from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from asistencia.models import Trabajador, ResumenAsistenciaDiaria, CierreAsistencia, MarcacionBiometrica
from asistencia.services.reglas_jornada import programacion_descanso
from asistencia.services.revision import puede_aprobar, detalle_jornada, marcas_persona
from asistencia.services.aprobacion_situacion import aprobar_situacion_del_dia

@transaction.atomic
def validar_descansos(trabajador, desde, hasta, actor):
    if not puede_aprobar(actor):
        raise ValidationError('Solo Contabilidad o Gerencia puede validar descansos.')
    if not 0 <= (hasta-desde).days <= 365:
        raise ValidationError('Seleccione un intervalo de hasta 366 días.')
    Trabajador.objects.select_for_update().get(pk=trabajador.pk)
    aprobadas = omitidas = 0
    cierres = list(CierreAsistencia.objects.all())
    for i in range((hasta-desde).days+1):
        fecha = desde + timedelta(days=i)
        if fecha > timezone.localdate() or any(c.fecha_inicio <= fecha <= c.fecha_fin for c in cierres):
            continue
        r = ResumenAsistenciaDiaria.objects.filter(trabajador=trabajador, fecha=fecha).first()
        candidato = r or ResumenAsistenciaDiaria(trabajador=trabajador, fecha=fecha, marcaciones_publicadas=[])
        regla = programacion_descanso(candidato)
        if not regla:
            continue
        if (r and (r.verificado_contabilidad or r.incidencias.exists() or r.ajustes.exists() or r.horas_trabajadas or any(m.es_valida for m in detalle_jornada(r, incluir_formulario=False)['marcas']))) or MarcacionBiometrica.objects.filter(marcas_persona(candidato), fecha_hora__date=fecha, es_valida=True).exists():
            omitidas += 1
            continue
        if r is None:
            r = ResumenAsistenciaDiaria.objects.create(trabajador=trabajador, fecha=fecha, marcaciones_publicadas=[], estado='POR_REVISAR')
        aprobar_situacion_del_dia(r, actor, 'SIN_PROGRAMACION' if regla.sin_trabajo_programado else 'DESCANSO_SEMANAL')
        r.conceptos_editados['descanso_validado_programacion'] = regla.pk
        r.save(update_fields=['conceptos_editados'])
        aprobadas += 1
    return aprobadas, omitidas
