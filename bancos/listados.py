from datetime import datetime
from django.db.models import Count
from django.db.models.functions import TruncMonth
from .models import EstadoCuenta


def contexto_importador(request, seleccionado=None):
    base = EstadoCuenta.objects.all()
    meses = list(base.annotate(mes=TruncMonth('inicio')).values('mes').annotate(archivos=Count('pk', distinct=True), total=Count('movimientos')).order_by('-mes'))
    for item in meses:
        item['valor'] = item['mes'].strftime('%Y-%m')
    mes = request.GET.get('mes', seleccionado.inicio.strftime('%Y-%m') if seleccionado else '')
    estados = base
    try:
        if mes:
            fecha = datetime.strptime(mes, '%Y-%m').date()
            estados = estados.filter(inicio__year=fecha.year, inicio__month=fecha.month)
    except ValueError:
        mes = ''
    counts = {'todos': estados.count(), 'pendientes': estados.filter(estado='PENDIENTE').count(), 'validados': estados.filter(estado='VALIDADO').count()}
    situacion = request.GET.get('situacion', '')
    if situacion in ('PENDIENTE', 'VALIDADO'):
        estados = estados.filter(estado=situacion)
    estados = estados.annotate(cantidad=Count('movimientos')).select_related('creado_por')
    archivo = request.GET.get('archivo', '')
    estado = seleccionado or (estados.filter(pk=archivo).first() if archivo.isdigit() else None) or estados.first()
    consulta = request.GET.copy()
    consulta.pop('page', None)
    consulta.pop('editar', None)
    if estado:
        consulta['archivo'] = str(estado.pk)
    return {'meses': meses, 'mes': mes, 'situacion': situacion, 'estados': estados, 'estado': estado, 'counts': counts,
        'total_archivos': base.count(), 'consulta': consulta.urlencode(), 'q': request.GET.get('q', '')[:200]}
