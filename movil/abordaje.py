"""Datos de abordaje y manifiesto; consulta sin alterar reservas ni reportes."""
from django.conf import settings
from django.utils import timezone


def puede_modificar(op):
    return (op.estado in ('PROGRAMADO', 'EN_CURSO')
            and not op.salida.anulado
            and op.salida.estado_operativo != 'CANCELADO'
            and (op.estado == 'EN_CURSO'
                 or op.salida.fecha >= timezone.localdate()))


def panel_abordaje(perfil, mes=None):
    from datetime import date
    from django.db.models import Q, Count
    from .models import Operacion
    from .views import VENTAS, exigir, nombre
    from .descanso_publicacion import estado_publicacion
    hoy = timezone.localdate()
    if mes:
        exigir(isinstance(mes, str) and len(mes) == 7 and mes[4] == '-'
               and mes[:4].isdigit() and mes[5:].isdigit(), 'Mes inválido.', 422)
        inicio_mes = date(int(mes[:4]), int(mes[5:]), 1)
        fin_mes = (inicio_mes.replace(year=inicio_mes.year + 1, month=1)
                   if inicio_mes.month == 12
                   else inicio_mes.replace(month=inicio_mes.month + 1))
    else:
        inicio_mes, fin_mes = None, None
    operaciones = Operacion.objects.select_related(
        'salida__importacion', 'salida__conductor_uno',
        'salida__conductor_dos').filter(
            salida__importacion__estado='VALIDADO',
            salida__anulado=False).exclude(
                estado='CANCELADO').exclude(salida__estado_operativo='CANCELADO')
    if perfil.usuario.rol not in VENTAS:
        permiso = Q(embarcadores=perfil)
        if perfil.conductor_id:
            permiso |= (Q(salida__conductor_uno_id=perfil.conductor_id)
                        | Q(salida__conductor_dos_id=perfil.conductor_id))
        operaciones = operaciones.filter(permiso)
    if inicio_mes:
        operaciones = operaciones.filter(
            salida__fecha__gte=inicio_mes, salida__fecha__lt=fin_mes)
    else:
        operaciones = operaciones.filter(
            Q(salida__fecha__gte=hoy) | Q(estado='EN_CURSO'))
    operaciones = operaciones.annotate(
            registrados=Count('pasajeros', distinct=True,
                              filter=~Q(pasajeros__estado='CANCELADO')),
            abordados=Count('pasajeros', distinct=True,
                           filter=Q(pasajeros__estado='EMBARCADO')),
            pendientes=Count('pasajeros', distinct=True,
                            filter=Q(pasajeros__estado='PENDIENTE')),
            ocupados=Count('pasajeros', distinct=True,
                          filter=Q(pasajeros__estado__in=('PENDIENTE', 'EMBARCADO'))),
        ).order_by('salida__fecha', 'salida__hora', 'pk')
    viajes = []
    for op in operaciones[:500]:
        if not estado_publicacion(op)[0]:
            continue
        s = op.salida
        config = op.distribucion_asientos or {}
        capacidad = (int(config.get('piso1', 0)) + int(config.get('piso2', 0))
                     if config.get('confirmada') else s.comercial.get('capacidad'))
        viajes.append({'id': op.pk, 'fecha': str(s.fecha),
                       'hora': s.hora.strftime('%H:%M'), 'bus': s.bus,
                       'origen': s.origen, 'destino': s.destino,
                       'estado': op.estado, 'capacidad': capacidad,
                       'registrados': op.registrados, 'abordados': op.abordados,
                       'pendientes': op.pendientes, 'ocupados': op.ocupados})
    return {'hoy': str(hoy), 'mes': mes or hoy.strftime('%Y-%m'),
            'operario': nombre(perfil), 'viajes': viajes, 'limite': 500}


def detalle_abordaje(op, perfil):
    from .views import embarque, nombre
    from .models import Perfil
    salida = op.salida
    conductores = []
    for conductor in (salida.conductor_uno, salida.conductor_dos):
        dni = ''
        if conductor:
            if conductor.trabajador_id:
                dni = conductor.trabajador.dni or ''
            else:
                cuenta = Perfil.objects.select_related('usuario').filter(
                    conductor=conductor).first()
                if cuenta:
                    dni = cuenta.usuario.dni or ''
        conductores.append({'nombre': str(conductor) if conductor else '',
                            'dni': dni})
    responsables = [nombre(p) for p in op.embarcadores.select_related(
        'usuario', 'trabajador').all()]
    pasajeros = list(op.pasajeros.order_by('piso', 'asiento', 'pk').values(
        'id', 'referencia', 'nombre', 'documento', 'edad', 'piso', 'asiento',
        'origen', 'destino', 'punto', 'punto_desembarque', 'estado'))
    distribucion = op.distribucion_asientos or {}
    capacidad = (int(distribucion.get('piso1', 0))
                 + int(distribucion.get('piso2', 0))) if distribucion.get(
                     'confirmada') else salida.comercial.get('capacidad')
    return {
        'hoy': str(timezone.localdate()),
        'consultado_el': timezone.localtime().isoformat(),
        'puede_modificar': bool(embarque(op, perfil) and puede_modificar(op)),
        'empresa': {
            'nombre': getattr(settings, 'SISMOC_EMPRESA_NOMBRE',
                              'Empresa de Transportes El Cumbe S.A.C.'),
            'ruc': getattr(settings, 'SISMOC_EMPRESA_RUC', ''),
            'direccion': getattr(settings, 'SISMOC_EMPRESA_DIRECCION', ''),
        },
        'operario': nombre(perfil),
        'viaje': {'id': op.pk, 'fecha': str(salida.fecha),
                  'hora': salida.hora.strftime('%H:%M'), 'bus': salida.bus,
                  'origen': salida.origen, 'destino': salida.destino,
                  'estado': op.estado, 'capacidad': capacidad,
                  'conductores': conductores, 'responsables': responsables},
        'pasajeros': pasajeros, 'distribucion': distribucion,
    }
