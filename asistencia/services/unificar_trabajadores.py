"""Unificación explícita de fichas duplicadas, preservando marcas y auditoría."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from asistencia.models import (Trabajador, IdentidadBiometrica, ResumenAsistenciaDiaria,
    ProgramacionHorario, IncidenciaAsistencia, AjusteAsistencia, RevisionAsistencia)
from asistencia.services.revision import comprobar_abierto, dejar_pendiente, registrar_historial


@transaction.atomic
def unificar_trabajadores(destino_id, origen_id, actor):
    if destino_id == origen_id:
        raise ValidationError('Seleccione dos fichas distintas.')
    fichas = {f.pk: f for f in Trabajador.objects.select_for_update().filter(pk__in=[destino_id, origen_id])}
    destino, origen = fichas[destino_id], fichas[origen_id]
    if origen.usuario_id and origen.usuario_id != destino.usuario_id:
        raise ValidationError('Las fichas tienen cuentas de acceso distintas; revise la vinculación.')
    jornadas = list(ResumenAsistenciaDiaria.objects.select_for_update().filter(trabajador_id__in=fichas).order_by('fecha', 'pk'))
    for r in jornadas:
        comprobar_abierto(r.fecha)
        if r.verificado_contabilidad:
            raise ValidationError('Reabra las jornadas aprobadas antes de unificar las fichas.')
        if (r.turno_aplicado_id and r.turno_aplicado.hora_salida < r.turno_aplicado.hora_entrada) or (r.primera_entrada and r.ultima_salida and r.ultima_salida < r.primera_entrada):
            raise ValidationError('La unificación de jornadas nocturnas requiere conciliar sus límites antes de continuar.')
    por_fecha = {r.fecha: r for r in jornadas if r.trabajador_id == destino_id}
    for r in jornadas:
        if r.trabajador_id != origen_id:
            continue
        conservada = por_fecha.get(r.fecha)
        if conservada:
            if r.conceptos_editados and conservada.conceptos_editados and r.conceptos_editados != conservada.conceptos_editados:
                raise ValidationError('Hay tiempos editados distintos en la misma fecha; concílielos antes de unificar.')
            if r.turno_aplicado_id and conservada.turno_aplicado_id and r.turno_aplicado_id != conservada.turno_aplicado_id:
                raise ValidationError('Hay horarios distintos en la misma fecha; concílielos antes de unificar.')
            conservada.conceptos_editados = conservada.conceptos_editados or r.conceptos_editados
            conservada.turno_aplicado_id = conservada.turno_aplicado_id or r.turno_aplicado_id
            if conservada.marcaciones_publicadas is None or r.marcaciones_publicadas is None:
                conservada.marcaciones_publicadas = None
            else:
                conservada.marcaciones_publicadas = sorted(set(conservada.marcaciones_publicadas + r.marcaciones_publicadas))
            conservada.observaciones += '\nFicha unificada: ' + r.observaciones
            conservada.save(update_fields=['conceptos_editados', 'turno_aplicado', 'marcaciones_publicadas', 'observaciones'])
            for modelo in (IncidenciaAsistencia, AjusteAsistencia, RevisionAsistencia):
                modelo.objects.filter(resumen=r).update(resumen=conservada)
            r.delete()
        else:
            r.trabajador = destino
            r.save(update_fields=['trabajador'])
            por_fecha[r.fecha] = r
    for p in ProgramacionHorario.objects.filter(trabajador=origen):
        otra = ProgramacionHorario.objects.filter(trabajador=destino, fecha=p.fecha).first()
        if otra:
            if otra.turno_id != p.turno_id:
                raise ValidationError('Hay programaciones incompatibles; revise los horarios antes de unificar.')
            p.delete()
        else:
            p.trabajador = destino
            p.save(update_fields=['trabajador'])
    IdentidadBiometrica.objects.filter(trabajador=origen).update(trabajador=destino)
    from asistencia.models import MarcacionBiometrica
    from django.db.models import Q
    for r in por_fecha.values():
        marcas = MarcacionBiometrica.objects.filter(
            Q(identidad_biometrica__trabajador=destino) | Q(filas_origen__identidad__trabajador=destino),
            es_valida=True).distinct()
        if r.marcaciones_publicadas is not None:
            marcas = marcas.filter(pk__in=r.marcaciones_publicadas)
        # Estas fichas se unifican sin inferir turnos nocturnos nuevos.
        marcas = list(marcas.filter(fecha_hora__date=r.fecha).order_by('fecha_hora', 'pk'))
        if marcas:
            r.primera_entrada = timezone.localtime(marcas[0].fecha_hora).time()
            r.ultima_salida = timezone.localtime(marcas[-1].fecha_hora).time() if len(marcas) > 1 else None
            r.save(update_fields=['primera_entrada', 'ultima_salida'])
        dejar_pendiente(r, actor, f'Unificación de fichas {origen.pk} ({origen.dni}) y {destino.pk} ({destino.dni}). Se conservan marcas y procedencia; revisar eventos.')
    registrar_historial(None, actor, 'Fichas de trabajador unificadas', f'{origen.pk}: {origen.nombre_completo}, DNI {origen.dni} → {destino.pk}: {destino.nombre_completo}, DNI {destino.dni}.')
    origen.delete()
    return len(por_fecha)
