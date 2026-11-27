"""Revisión reversible de marcas cercanas; las fuentes nunca se eliminan."""
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from asistencia.models import MarcacionBiometrica, RevisionAsistencia
from asistencia.services.revision import comprobar_abierto, dejar_pendiente, detalle_jornada, puede_gestionar, registrar_historial

VENTANA_SEGUNDOS = 60  # Solo aviso de proximidad, nunca una decisión automática.
EXCLUIR = 'Marcación excluida por duplicada'
RESTAURAR = 'Marcación duplicada restaurada'


def pares_cercanos(marcas):
    validas = sorted((m for m in marcas if m.es_valida), key=lambda m: (m.fecha_hora, m.pk))
    pares = {}
    for anterior, actual in zip(validas, validas[1:]):
        if actual.fecha_hora - anterior.fecha_hora <= timedelta(seconds=VENTANA_SEGUNDOS):
            pares.setdefault(anterior.pk, actual.pk)
            pares.setdefault(actual.pk, anterior.pk)
    return pares


def ultimas_revisiones(marcas):
    revisiones = RevisionAsistencia.objects.filter(marcacion_id__in=[m.pk for m in marcas], accion__in=[EXCLUIR, RESTAURAR]).order_by('-fecha', '-pk')
    ultimas = {}
    for rev in revisiones:
        ultimas.setdefault(rev.marcacion_id, rev.accion)
    return ultimas


@transaction.atomic
def revisar_duplicada(resumen, actor, marcacion_id, restaurar=False):
    if not puede_gestionar(actor):
        raise ValidationError('No tiene permiso para revisar marcaciones duplicadas.')
    comprobar_abierto(resumen.fecha)
    marcas = detalle_jornada(resumen, incluir_formulario=False)['marcas']
    if marcacion_id not in {m.pk for m in marcas}:
        raise ValidationError('La marcación no pertenece a esta jornada o al archivo publicado.')
    marca = MarcacionBiometrica.objects.select_for_update().get(pk=marcacion_id)
    if restaurar:
        if marca.es_valida or ultimas_revisiones([marca]).get(marca.pk) != EXCLUIR:
            raise ValidationError('Solo puede restaurar una marca excluida por duplicada. Actualice la ventana.')
        detalle = 'Marca restaurada por revisión. Vuelve a participar en la validación y el cálculo.'
    else:
        companera = pares_cercanos(marcas).get(marca.pk)
        if not marca.es_valida or not companera:
            raise ValidationError('No hay otra marca válida a 60 segundos o menos en esta jornada. Actualice la ventana y revise las marcas.')
        # Bloquear también la compañera evita excluir ambas por revisiones simultáneas.
        conservada = MarcacionBiometrica.objects.select_for_update().get(pk=companera)
        if not conservada.es_valida:
            raise ValidationError('La otra marca ya fue excluida. Actualice la ventana.')
        detalle = f'Repetición confirmada por revisión. Se conserva la marca #{companera}. La fuente original permanece guardada.'
    marca.es_valida = restaurar
    marca.save(update_fields=['es_valida'])
    registrar_historial(resumen, actor, RESTAURAR if restaurar else EXCLUIR, f'{marca.fecha_hora.isoformat()} · {detalle}', marca)
    dejar_pendiente(resumen, actor, 'Se restauró una marca duplicada.' if restaurar else 'Se excluyó una marca duplicada; confirme los eventos restantes.')
    from asistencia.services.revision_trabajador import validar_periodo
    d = detalle_jornada(resumen, incluir_formulario=False)
    if not d['completa'] and not resumen.ajustes.exists():
        campos = ['horas_trabajadas', 'horas_extras_25', 'horas_extras_35', 'horas_nocturnas']
        for campo in campos:
            setattr(resumen, campo, 0)
        resumen.save(update_fields=campos)
    validar_periodo([resumen], {}, {}, None, 'Revisión de marca duplicada; aprobación pendiente.', actor)
