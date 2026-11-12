from collections import Counter
from datetime import datetime
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from .models import Importacion, Salida
from .parser import identidad, normalizar
from .services import problemas


def listado_importaciones(request, pendientes=False):
    base = Salida.objects.all()
    if pendientes:
        base = base.filter(importacion__estado='PENDIENTE')
    meses = list(base.annotate(mes=TruncMonth('fecha')).values('mes').annotate(total=Count('pk')).order_by('-mes'))
    mes = request.GET.get('mes', '')
    try:
        fecha = datetime.strptime(mes, '%Y-%m').date() if mes else None
    except ValueError:
        fecha, mes = None, ''
    for item in meses:
        item['valor'] = item['mes'].strftime('%Y-%m')
    filtradas = base
    if fecha:
        filtradas = filtradas.filter(fecha__year=fecha.year, fecha__month=fecha.month)
    archivos = Importacion.objects.filter(pk__in=filtradas.values('importacion_id')).order_by('-fin')
    archivo = request.GET.get('archivo', '')
    if archivo.isdigit():
        filtradas = filtradas.filter(importacion_id=int(archivo))
    else:
        archivo = ''
    grupos = {}
    for salida in filtradas.filter(anulado=False).select_related('importacion', 'conductor_uno__trabajador', 'conductor_dos__trabajador'):
        for nombre, conductor in ((salida.nombre_uno, salida.conductor_uno), (salida.nombre_dos, salida.conductor_dos)):
            key = (salida.importacion_id, identidad(nombre))
            if key not in grupos:
                grupos[key] = {'nombre': nombre or 'Sin nombre en el reporte', 'conductor': conductor,
                    'lote': salida.importacion, 'trayectos': 0}
            grupos[key]['trayectos'] += 1
            if conductor is None:
                grupos[key]['conductor'] = None
    filas = list(grupos.values())
    q = request.GET.get('q', '').strip()[:180]
    if q:
        tokens = normalizar(q).split()
        filas = [f for f in filas if all(t in normalizar(f['nombre']+' '+(f['conductor'].nombre_apellidos if f['conductor'] else '')) for t in tokens)]
    totales = Counter('reconocidos' if f['conductor'] else 'pendientes' for f in filas)
    estado = request.GET.get('estado', '')
    if estado in ('pendientes', 'reconocidos'):
        filas = [f for f in filas if bool(f['conductor']) == (estado == 'reconocidos')]
    filas.sort(key=lambda f: normalizar(f['conductor'].nombre_apellidos if f['conductor'] else f['nombre']))
    salidas = list(filtradas.select_related('importacion', 'conductor_uno__trabajador', 'conductor_dos__trabajador').order_by('importacion_id', 'fila', 'pk'))
    if q:
        salidas = [s for s in salidas if all(t in normalizar(' '.join((s.bus, s.origen, s.destino, s.nombre_uno, s.nombre_dos))) for t in normalizar(q).split())]
    pendientes_validar = sum(not s.anulado and s.importacion.estado == 'PENDIENTE' for s in salidas)
    validadas = sum(not s.anulado and s.importacion.estado == 'VALIDADO' for s in salidas)
    anuladas = sum(s.anulado for s in salidas)
    total_filas = len(salidas)
    if estado == 'por_validar':
        salidas = [s for s in salidas if not s.anulado and s.importacion.estado == 'PENDIENTE']
    elif estado == 'validadas':
        salidas = [s for s in salidas if not s.anulado and s.importacion.estado == 'VALIDADO']
    elif estado == 'anuladas':
        salidas = [s for s in salidas if s.anulado]
    lotes = list(archivos.filter(pk__in=filtradas.values('importacion_id')))
    revisiones = [{'lote': l, 'errores': problemas(l) if l.estado == 'PENDIENTE' else []} for l in lotes]
    return dict(meses=meses, mes=mes, archivos=archivos, archivo_seleccionado=archivo, q=q, estado_filtro=estado,
        identidades=filas, total_identidades=sum(totales.values()), reconocidos=totales['reconocidos'], pendientes_total=totales['pendientes'],
        total_salidas=filtradas.filter(anulado=False).count(), total_registros=base.count(),
        lotes=lotes, revisiones=revisiones, pagina_salidas=Paginator(salidas, 60).get_page(request.GET.get('pagina')),
        total_filas=total_filas, pendientes_validar=pendientes_validar, validadas=validadas, anuladas=anuladas)
