"""Agrupar por fecha real de las marcas y conservar la procedencia de cada carga."""
from calendar import monthrange
from datetime import date
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from asistencia.models import MarcacionBiometrica, CargaArchivoAsistencia, FilaImportacionBiometrica

MESES=('Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre')


def grupo_importacion(parametros):
    # Subconsultas de IDs evitan multiplicar las filas de ambas procedencias.
    base=MarcacionBiometrica.objects.filter(Q(pk__in=FilaImportacionBiometrica.objects.values('marcacion_id'))|Q(carga_origen__isnull=False))
    carga_texto=parametros.get('grupo_carga','').strip()
    error=''
    carga=None
    if carga_texto:
        if not carga_texto.isdigit(): error='Seleccione un archivo válido.'
        else:
            carga=CargaArchivoAsistencia.objects.filter(pk=int(carga_texto),estado='COMPLETADO').first()
            if not carga: error='El archivo seleccionado no está disponible.'
    archivos_base=base.filter(Q(filas_origen__carga=carga)|Q(carga_origen=carga)) if carga else base
    meses=list(base.annotate(mes=TruncMonth('fecha_hora')).values('mes').annotate(total=Count('pk',distinct=True)).order_by('-mes'))
    ultimo=archivos_base.order_by('-fecha_hora').values_list('fecha_hora',flat=True).first()
    from django.utils import timezone
    mes=parametros.get('grupo_mes','').strip() or (timezone.localtime(ultimo).strftime('%Y-%m') if ultimo else '')
    todos = mes == 'todos'
    inicio=fin=None
    if mes and not todos:
        try:
            inicio=date.fromisoformat(mes+'-01')
            if inicio.strftime('%Y-%m')!=mes: raise ValueError
            fin=inicio.replace(day=monthrange(inicio.year,inicio.month)[1])
        except ValueError:
            error='Seleccione un mes válido.'
    marcas=archivos_base
    if inicio: marcas=marcas.filter(fecha_hora__date__range=(inicio,fin))
    if error: marcas=marcas.none()
    del_mes=base if todos else (base.filter(fecha_hora__date__range=(inicio,fin)) if inicio else base.none())
    cargas=CargaArchivoAsistencia.objects.filter(
        Q(pk__in=FilaImportacionBiometrica.objects.filter(marcacion__in=del_mes).values('carga_id')) |
        Q(pk__in=del_mes.values('carga_origen_id'))
    ) if inicio or todos else CargaArchivoAsistencia.objects.none()
    return {'todos':todos,'total_marcas':sum(m['total'] for m in meses),'mes':mes,'carga_id':carga_texto,'carga':carga,'inicio':inicio,'fin':fin,'marcas':marcas,'fuente':archivos_base.none() if error else archivos_base,'activo':bool(meses or carga_texto or mes),'error':error,'meses':[{'valor':m['mes'].strftime('%Y-%m'),'nombre':f"{MESES[m['mes'].month-1]} {m['mes'].year}",'total':m['total']} for m in meses],'cargas':cargas.order_by('-fecha_subida')}


def validar_grupo_envio(parametros, desde, hasta):
    grupo=grupo_importacion(parametros)
    if grupo['error']: raise ValidationError(grupo['error'])
    if grupo['activo']:
        if not grupo['todos'] and (not grupo['inicio'] or not grupo['inicio'] <= desde <= hasta <= grupo['fin']):
            raise ValidationError('El rango de envío debe estar dentro del mes seleccionado.')
        if not grupo['marcas'].exists(): raise ValidationError('No hay marcaciones en el grupo seleccionado.')
    return grupo
