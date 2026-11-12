"""Registro explícito de una marcación faltante, con procedencia y auditoría."""
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone
from asistencia.forms import MarcacionManualForm
from asistencia.models import MarcacionBiometrica, ResumenAsistenciaDiaria
from asistencia.services.revision import comprobar_abierto, detalle_jornada, marcas_persona, ventana_jornada, registrar_historial, dejar_pendiente
from asistencia.services.revision_trabajador import filtrar_persona, validar_periodo


def agregar_marcacion_manual(resumen, datos, actor, *, marcacion=None):
    """El llamador bloquea la jornada y mantiene una transacción."""
    if marcacion and (marcacion.origen != 'SISTEMA_MANUAL' or not marcacion.es_valida
            or marcacion.pk not in [m.pk for m in detalle_jornada(resumen)['marcas']]):
        raise ValidationError('Solo puede editar una marcación manual válida de esta jornada.')
    formulario = MarcacionManualForm(datos, resumen=resumen)
    if not formulario.is_valid():
        raise ValidationError([f"{formulario.fields[campo].label}: {mensaje}" for campo, mensajes in formulario.errors.items() for mensaje in mensajes])
    valores = formulario.cleaned_data
    fecha = valores["fecha_manual"]
    instante = timezone.make_aware(datetime.combine(fecha, valores["hora_manual"]))
    if fecha not in {resumen.fecha, resumen.fecha + timedelta(days=1)}:
        raise ValidationError("La fecha debe corresponder a la jornada o al día siguiente si cruza medianoche.")
    if instante > timezone.now():
        raise ValidationError("No se puede agregar una marcación con fecha u hora futura.")
    comprobar_abierto(resumen.fecha)
    comprobar_abierto(fecha)
    if detalle_jornada(resumen)["situacion_dia"]:
        raise ValidationError("El día tiene una situación de no laborado registrada. Revise esa situación antes de agregar trabajo.")
    identidad = valores["identidad_manual"]
    if resumen.trabajador_id and identidad is None:
        raise ValidationError("Seleccione el código importado que identifica al trabajador.")
    if MarcacionBiometrica.objects.filter(marcas_persona(resumen), fecha_hora=instante, es_valida=True).exclude(pk=marcacion.pk if marcacion else None).exists():
        raise ValidationError("El trabajador ya tiene una marcación a esa fecha y hora. Corrija el tipo de la existente.")
    otras = filtrar_persona(ResumenAsistenciaDiaria.objects.all(), resumen.persona.dni).filter(fecha__range=(resumen.fecha - timedelta(days=1), fecha)).exclude(pk=resumen.pk)
    for otra in otras:
        if not detalle_jornada(otra, incluir_formulario=False)['marcas'] and not otra.incidencias.exists() and not otra.ajustes.exists():
            continue
        inicio, fin = ventana_jornada(otra)
        if inicio <= instante <= fin:
            raise ValidationError("La hora corresponde al intervalo de otra jornada del trabajador. Agréguela en el día correcto.")
    originales = detalle_jornada(resumen)["marcas"]
    entradas = [m.fecha_hora for m in originales if m.es_valida and m.evento_efectivo == 'ENTRADA' and (not marcacion or m.pk != marcacion.pk)]
    if valores['tipo_evento_manual'] != 'ENTRADA' and entradas and instante <= min(entradas):
        raise ValidationError('La marcación no puede ser anterior a la entrada. Si corresponde a la madrugada del turno nocturno, seleccione la fecha del día siguiente.')
    instantes = [m.fecha_hora for m in originales if m.es_valida and (not marcacion or m.pk != marcacion.pk)] + [instante]
    primera, ultima = min(instantes), max(instantes)
    if timezone.localtime(primera).date() != resumen.fecha or ultima - primera >= timedelta(days=1):
        raise ValidationError("La marcación produciría una jornada de 24 horas o más, o una entrada en otro día. Revise la fecha y hora.")
    codigo = identidad.codigo if identidad else None
    anterior = ''
    if marcacion:
        anterior = f'Antes: {timezone.localtime(marcacion.fecha_hora).isoformat()} · {marcacion.get_tipo_evento_display()} · {marcacion.motivo_manual}. '
        marcacion.fecha_hora = instante
        marcacion.tipo_evento = valores['tipo_evento_manual']
        marcacion.motivo_manual = valores['motivo_manual']
        marcacion.save(update_fields=['fecha_hora', 'tipo_evento', 'motivo_manual'])
        correccion = getattr(marcacion, 'correccion_evento', None)
        if correccion:
            correccion.tipo_evento = valores['tipo_evento_manual']
            correccion.motivo = valores['motivo_manual']
            correccion.responsable = actor
            correccion.save(update_fields=['tipo_evento','motivo','responsable'])
        marca = marcacion
    else:
        marca = MarcacionBiometrica.objects.create(
            usuario_id=resumen.usuario_id, identidad_biometrica=identidad,
            dni=resumen.persona.dni, nombre_empleado=resumen.persona.nombre_completo,
            zkteco_user_id=int(codigo) if codigo and codigo.isdigit() and len(codigo) <= 9 else None,
            fecha_hora=instante, tipo_evento=valores["tipo_evento_manual"], origen="SISTEMA_MANUAL",
            registrada_por=actor, motivo_manual=valores["motivo_manual"], evidencia_manual_url=valores["evidencia_manual_url"],
        )
    resumen.primera_entrada = timezone.localtime(primera).time()
    if resumen.marcaciones_publicadas is not None and not marcacion:
        resumen.marcaciones_publicadas = [*resumen.marcaciones_publicadas, marca.pk]
    resumen.ultima_salida = timezone.localtime(ultima).time() if primera != ultima else None
    resumen.save(update_fields=["primera_entrada", "ultima_salida", "marcaciones_publicadas"])
    registrar_historial(resumen, actor, "Marcación manual editada" if marcacion else "Marcación manual agregada", f"{anterior}{instante.isoformat()} · {marca.get_tipo_evento_display()} · {valores['motivo_manual']}", marca)
    dejar_pendiente(resumen, actor, "Se agregó una marcación manual; requiere revisión de la jornada.")
    validar_periodo([resumen], {}, {}, None, "Recalculado tras agregar marcación manual.", actor)
    return marca
