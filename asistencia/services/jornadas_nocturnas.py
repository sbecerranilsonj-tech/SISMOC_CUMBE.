"""Reagrupar jornadas ya publicadas tras confirmar su horario nocturno."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from asistencia.models import ResumenAsistenciaDiaria, MarcacionBiometrica, FilaImportacionBiometrica
from asistencia.services.revision import comprobar_abierto, detalle_jornada, marcas_persona, dejar_pendiente, registrar_historial


def corte_descanso(turno):
    minutos = ((turno.hora_salida.hour * 60 + turno.hora_salida.minute) + (turno.hora_entrada.hour * 60 + turno.hora_entrada.minute)) // 2
    return time(minutos // 60, minutos % 60)


def _guardar_grupo(resumen, marcas, actor, destino, *, sin_entrada=False):
    """Conservar la fuente y el historial; nunca aprobar ni clasificar eventos."""
    marcas = sorted(marcas, key=lambda m: (m.fecha_hora, m.pk))
    anterior = f'IDs: {resumen.marcaciones_publicadas}; límites: {resumen.primera_entrada}–{resumen.ultima_salida}; horas: {resumen.horas_trabajadas}; extras: {resumen.horas_extras_25}/{resumen.horas_extras_35}; nocturnas: {resumen.horas_nocturnas}'
    resumen.marcaciones_publicadas = [m.pk for m in marcas]
    resumen.primera_entrada = timezone.localtime(marcas[0].fecha_hora).time() if marcas else None
    resumen.ultima_salida = timezone.localtime(marcas[-1].fecha_hora).time() if len(marcas) > 1 else None
    if sin_entrada:
        resumen.conceptos_editados['inicio_archivo_sin_entrada'] = True
        resumen.primera_entrada = None
        resumen.ultima_salida = timezone.localtime(marcas[-1].fecha_hora).time()
    else:
        resumen.conceptos_editados.pop('inicio_archivo_sin_entrada', None)
    for campo in ('horas_trabajadas', 'horas_extras_25', 'horas_extras_35', 'horas_nocturnas'):
        setattr(resumen, campo, Decimal(0))
    resumen.estado = 'POR_REVISAR'
    resumen.minutos_tardanza = 0
    resumen.save(update_fields=['conceptos_editados', 'marcaciones_publicadas', 'primera_entrada', 'ultima_salida', 'estado', 'minutos_tardanza', 'horas_trabajadas', 'horas_extras_25', 'horas_extras_35', 'horas_nocturnas'])
    registrar_historial(resumen, actor, 'Jornada nocturna reagrupada', f'Jornada de inicio: {destino}. Antes: {anterior}. Ahora IDs: {resumen.marcaciones_publicadas}. Fechas y eventos originales conservados.')
    dejar_pendiente(resumen, actor, 'Horario nocturno confirmado. Las marcas se agrupan por la fecha de inicio; confirme los eventos antes de aprobar.')
    # Solo reconstruir tiempos de eventos ya confirmados; las propuestas siguen sin guardar.
    from asistencia.services.revision_trabajador import validar_periodo
    validar_periodo([resumen], {}, {}, None, 'Revisión tras agrupar jornada nocturna.', actor)


@transaction.atomic
def reagrupar_nocturnas(trabajador, fechas, actor):
    consulta = Q(trabajador=trabajador)
    if trabajador.usuario_id:
        consulta |= Q(trabajador__isnull=True, usuario_id=trabajador.usuario_id)
    cambiadas = 0
    for fecha in sorted(fechas):
        r = ResumenAsistenciaDiaria.objects.select_for_update(of=('self',)).filter(consulta, fecha=fecha).first()
        if not r or not r.turno_aplicado_id or r.turno_aplicado.hora_salida >= r.turno_aplicado.hora_entrada:
            continue
        originales = detalle_jornada(r, incluir_formulario=False)['marcas']
        if not originales:
            continue
        corte = corte_descanso(r.turno_aplicado)
        inicio = timezone.make_aware(datetime.combine(fecha, corte))
        fin = timezone.make_aware(datetime.combine(fecha + timedelta(days=1), corte))
        tempranas = [m for m in originales if m.fecha_hora < inicio]
        if tempranas and not r.conceptos_editados.get('inicio_archivo_sin_entrada'):
            previa_fecha = fecha - timedelta(days=1)
            comprobar_abierto(previa_fecha)
            previa = ResumenAsistenciaDiaria.objects.select_for_update(of=('self',)).filter(consulta, fecha=previa_fecha).first()
            limite_previo = timezone.make_aware(datetime.combine(previa_fecha, corte))
            hay_entrada_previa = MarcacionBiometrica.objects.filter(marcas_persona(r), fecha_hora__gte=limite_previo, fecha_hora__lt=timezone.make_aware(datetime.combine(fecha, time.min)), es_valida=True).exists()
            previa_con_marcas = bool(previa and detalle_jornada(previa, incluir_formulario=False)['marcas'])
            if hay_entrada_previa or (previa and (previa.ajustes.exists() or previa.incidencias.exists() or previa.verificado_contabilidad or (previa_con_marcas and not previa.conceptos_editados.get('inicio_archivo_sin_entrada')))):
                raise ValidationError(f'Revise o programe la jornada del {previa_fecha:%d/%m/%Y}: hay registros anteriores que no pueden tratarse como inicio incompleto del archivo.')
            if r.ajustes.exists() or r.incidencias.exists():
                raise ValidationError('Concilie las incidencias y ajustes antes de separar la madrugada inicial.')
            if previa is None:
                previa = ResumenAsistenciaDiaria.objects.create(trabajador=trabajador, usuario_id=r.usuario_id, fecha=previa_fecha, turno_aplicado=r.turno_aplicado, estado='POR_REVISAR')
            if previa.turno_aplicado_id != r.turno_aplicado_id:
                previa.turno_aplicado = r.turno_aplicado
                previa.save(update_fields=['turno_aplicado'])
            anteriores = detalle_jornada(previa, incluir_formulario=False)['marcas'] if previa.conceptos_editados.get('inicio_archivo_sin_entrada') else []
            unidas = {m.pk: m for m in anteriores + tempranas}
            _guardar_grupo(previa, list(unidas.values()), actor, previa_fecha, sin_entrada=True)
            registrar_historial(previa, actor, 'Inicio de archivo incompleto', 'Marcación inicial sin pareja: no existe entrada de la noche anterior en los registros disponibles. Sin horas calculadas.')
            originales = [m for m in originales if m.pk not in unidas]
            _guardar_grupo(r, originales, actor, fecha)
            if not originales:
                continue
        fuentes = set(FilaImportacionBiometrica.objects.filter(marcacion__in=originales).values_list('carga_id', flat=True))
        fuentes.update(m.carga_origen_id for m in originales if m.carga_origen_id)
        candidatas = MarcacionBiometrica.objects.filter(marcas_persona(r), fecha_hora__gte=inicio, fecha_hora__lt=fin)
        if r.marcaciones_publicadas is not None:
            candidatas = candidatas.filter(Q(pk__in=r.marcaciones_publicadas) | Q(carga_origen_id__in=fuentes) | Q(filas_origen__carga_id__in=fuentes))
        candidatas = list(candidatas.select_related('identidad_biometrica', 'correccion_evento').prefetch_related('filas_origen__identidad').distinct().order_by('fecha_hora', 'pk'))
        if not candidatas or timezone.localtime(candidatas[0].fecha_hora).date() != fecha:
            continue
        if {m.pk for m in originales} == {m.pk for m in candidatas}:
            continue
        entradas_conflictivas = [m for m in candidatas if m.es_valida and timezone.localtime(m.fecha_hora).date() > fecha and getattr(getattr(m, 'correccion_evento', None), 'tipo_evento', m.tipo_evento) == 'ENTRADA']
        if entradas_conflictivas:
            fechas_conflictivas = ', '.join(timezone.localtime(m.fecha_hora).strftime('%d/%m/%Y a las %H:%M:%S') for m in entradas_conflictivas)
            raise ValidationError(f'No se pudo agrupar la jornada del {fecha:%d/%m/%Y} al {fecha + timedelta(days=1):%d/%m/%Y}: hay una entrada confirmada el {fechas_conflictivas}. Corrobore si corresponde a una salida de la noche anterior o a una entrada real antes de unir las jornadas.')
        for m in candidatas:
            propietarios = {f.identidad.trabajador_id for f in m.filas_origen.all() if f.identidad.trabajador_id}
            if m.identidad_biometrica_id and m.identidad_biometrica.trabajador_id:
                propietarios.add(m.identidad_biometrica.trabajador_id)
            if propietarios - {trabajador.pk} or (m.usuario_id and m.usuario_id != trabajador.usuario_id):
                raise ValidationError('Hay una marcación asociada a otro trabajador. Revise la identificación antes de reagrupar.')
            comprobar_abierto(timezone.localtime(m.fecha_hora).date())
        comprobar_abierto(fecha)
        movidas = {m.pk for m in candidatas} - {m.pk for m in originales}
        siguientes = list(ResumenAsistenciaDiaria.objects.select_for_update(of=('self',)).filter(consulta, fecha=fecha + timedelta(days=1)))
        cambios = []
        for otra in siguientes:
            actuales = detalle_jornada(otra, incluir_formulario=False)['marcas']
            restantes = [m for m in actuales if m.pk not in movidas]
            if len(restantes) != len(actuales):
                cambios.append((otra, restantes))
        for afectada in [r, *(otra for otra, _ in cambios)]:
            comprobar_abierto(afectada.fecha)
            if afectada.ajustes.exists() or afectada.incidencias.exists():
                raise ValidationError(f'La jornada {afectada.fecha:%d/%m/%Y} tiene incidencias o ajustes. Concilie esos registros antes de reagruparla.')
        for otra, restantes in cambios:
            _guardar_grupo(otra, restantes, actor, fecha)
        _guardar_grupo(r, candidatas, actor, fecha)
        cambiadas += 1
    return cambiadas
