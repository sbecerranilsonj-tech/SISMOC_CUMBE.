"""Preferencia individual y recálculo protegido de horas nocturnas."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from asistencia.models import Trabajador, ResumenAsistenciaDiaria, CierreAsistencia
from asistencia.services.reglas_jornada import nocturnas_automaticas
from asistencia.services.revision import puede_aprobar, registrar_historial
from asistencia.services.revision_trabajador import detalles_en_lote
from asistencia.services.cuadro_excel import segundos_nocturnos

@transaction.atomic
def configurar_nocturnas(trabajador, activo, actor):
    if not puede_aprobar(actor):
        raise ValidationError('La configuración corresponde a Contabilidad o Gerencia.')
    trabajador=Trabajador.objects.select_for_update().get(pk=trabajador.pk)
    jornadas=list(ResumenAsistenciaDiaria.objects.select_for_update(of=('self',)).filter(trabajador=trabajador).select_related('trabajador__usuario__turno','usuario__turno','turno_aplicado').prefetch_related('ajustes','incidencias'))
    cierres=list(CierreAsistencia.objects.all())
    for r in jornadas:
        cerrada=any(c.fecha_inicio<=r.fecha<=c.fecha_fin for c in cierres)
        if (r.verificado_contabilidad or cerrada) and 'nocturnas_automaticas' not in r.conceptos_editados:
            r.conceptos_editados['nocturnas_automaticas']=nocturnas_automaticas(r)
            # Fijar únicamente la política de visualización anterior: no recalcular
            # campos de horas ni modificar el estado de una jornada protegida.
            ResumenAsistenciaDiaria.objects.filter(pk=r.pk).update(conceptos_editados=r.conceptos_editados)
            registrar_historial(r,actor,'Política de nocturnas conservada',f'Jornada aprobada o cerrada: cálculo automático anterior={r.conceptos_editados["nocturnas_automaticas"]}. Tiempos y aprobación sin cambios.')
    anterior=trabajador.calcular_nocturnas
    trabajador.calcular_nocturnas=activo
    trabajador.save(update_fields=['calcular_nocturnas'])
    abiertas=[]
    for r in jornadas:
        if r.verificado_contabilidad or any(c.fecha_inicio<=r.fecha<=c.fecha_fin for c in cierres): continue
        if 'horas_nocturnas' in r.conceptos_editados or any(a.concepto=='horas_nocturnas' for a in r.ajustes.all()): continue
        r.trabajador=trabajador
        if 'nocturnas_automaticas' in r.conceptos_editados:
            r.conceptos_editados.pop('nocturnas_automaticas')
            r.save(update_fields=['conceptos_editados'])
        abiertas.append(r)
    actualizadas=0
    for d in detalles_en_lote(abiertas):
        r=d['resumen']
        segundos=segundos_nocturnos(d['tramos']) if activo and d['completa'] and not d['falta_refrigerio'] else 0
        valor=(Decimal(segundos)/Decimal(3600)).quantize(Decimal('.01'))
        if r.horas_nocturnas!=valor:
            antes=r.horas_nocturnas;r.horas_nocturnas=valor;r.save(update_fields=['horas_nocturnas'])
            registrar_historial(r,actor,'Nocturnas recalculadas',f'Antes: {antes}; ahora: {valor}. Preferencia individual automática={activo}.')
            actualizadas+=1
    registrar_historial(None,actor,'Configuración de nocturnas',f'Trabajador #{trabajador.pk} {trabajador.nombre_completo}: {anterior} → {activo}. {actualizadas} jornadas pendientes actualizadas; aprobadas, cerradas y manuales conservadas.')
    return actualizadas
