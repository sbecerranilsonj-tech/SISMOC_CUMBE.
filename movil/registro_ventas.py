from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.formats import date_format
from conductores.models import Salida


def contexto_registro(request):
    base=Salida.objects.select_related('importacion','conductor_uno','conductor_dos','operacion')
    # El itinerario es compartido; sede filtra el origen, no crea copias por usuario.
    filtros={k:request.GET.get(k,'').strip() for k in ('mes','archivo','q','estado','origen','desde','hasta')}
    meses=[]
    for m in base.annotate(mes=TruncMonth('fecha')).values('mes').annotate(total=Count('pk')).order_by('-mes'):
        valor=m['mes'].strftime('%Y-%m');meses.append({'valor':valor,'nombre':date_format(m['mes'],'F Y'),'total':m['total'],'url':'?'+urlencode({'mes':valor})})
    qs=base
    import re
    if re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',filtros['mes']):
        anio,mes=map(int,filtros['mes'].split('-'));qs=qs.filter(fecha__year=anio,fecha__month=mes)
    archivos=qs.values('importacion_id','importacion__nombre').distinct().order_by('importacion__nombre')
    if filtros['archivo'].isdigit():qs=qs.filter(importacion_id=filtros['archivo'])
    if filtros['origen']:qs=qs.filter(origen=filtros['origen'])
    from datetime import date
    for campo,lookup in [('desde','fecha__gte'),('hasta','fecha__lte')]:
        try:valor=date.fromisoformat(filtros[campo])
        except ValueError:continue
        qs=qs.filter(**{lookup:valor})
    if filtros['q']:
        q=filtros['q'];qs=qs.filter(Q(bus__icontains=q)|Q(origen__icontains=q)|Q(destino__icontains=q)|Q(nombre_uno__icontains=q)|Q(nombre_dos__icontains=q))
    anuladas=Q(anulado=True)|Q(estado_operativo='CANCELADO')
    conteos=qs.aggregate(total=Count('pk'),pendientes=Count('pk',filter=Q(importacion__estado='PENDIENTE')&~anuladas),validadas=Count('pk',filter=Q(importacion__estado='VALIDADO')&~anuladas),anuladas=Count('pk',filter=anuladas))
    if filtros['estado'] in ('PENDIENTE','por_validar'):qs=qs.filter(importacion__estado='PENDIENTE').exclude(anuladas)
    elif filtros['estado'] in ('CANCELADO','anuladas'):qs=qs.filter(anuladas)
    elif filtros['estado'] in ('VALIDADO','validadas'):qs=qs.filter(importacion__estado='VALIDADO').exclude(anuladas)
    parametros={k:v for k,v in filtros.items() if v}
    pagina=Paginator(qs.order_by('importacion_id','fila','pk'),50).get_page(request.GET.get('pagina'))
    hoy=timezone.localdate()
    for salida in pagina.object_list:
        operacion=getattr(salida,'operacion',None)
        cerrado=(salida.anulado or salida.estado_operativo in ('REALIZADO','CANCELADO')
                 or bool(operacion and operacion.estado == 'FINALIZADO'))
        salida.gestionable=salida.fecha >= hoy and not cerrado
    return {'registro_pagina':pagina, 'registro_total':base.count(),'registro_meses':meses,'registro_archivos':archivos,'registro_origenes':base.order_by('origen').values_list('origen',flat=True).distinct(),'filtros_ventas':filtros,'registro_query':urlencode(parametros),'total_filas':conteos['total'],'pendientes_validar':conteos['pendientes'],'validadas':conteos['validadas'],'anuladas':conteos['anuladas']}
