"""API exclusiva para la aplicación: bearer revocable, sin autenticación por cookie."""
import hashlib
import json
import math
import secrets
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from zoneinfo import ZoneInfo

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import (Perfil, Sesion, Zona, Comision, Registro, Solicitud, Operacion,
    EventoViaje, Descanso, ReglaDescanso, Pasajero, Incidencia, Pago, Aviso, Auditoria, IntentoAcceso)

PERU = ZoneInfo('America/Lima')
GESTION = {'CONTADORA', 'ADMINISTRADOR', 'GERENTE_GENERAL'}
VENTAS = GESTION | {'BOLETERIA'}
TIPOS = ['ENTRADA', 'SALIDA_REFRIGERIO', 'RETORNO_REFRIGERIO', 'SALIDA']

class Problema(Exception):
    def __init__(self, mensaje, status=400):
        self.mensaje, self.status = mensaje, status

def exigir(condicion, mensaje, status=400):
    if not condicion:
        raise Problema(mensaje, status)

def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()

def fecha(valor):
    return date.fromisoformat(str(valor))

def instante(valor):
    t = datetime.fromisoformat(str(valor).replace('Z', '+00:00'))
    exigir(timezone.is_aware(t), 'La fecha debe incluir zona horaria.')
    return t

def rol(p, roles):
    exigir(p.usuario.rol in roles, 'No tiene permiso para esta acción.', 403)

def nombre(p):
    return p.trabajador.nombre_completo if p.trabajador_id else (p.usuario.get_full_name() or p.codigo)

def asignado(op, p):
    return p.conductor_id and p.conductor_id in (op.salida.conductor_uno_id, op.salida.conductor_dos_id)

def embarque(op, p):
    return p.usuario.rol in VENTAS or op.embarcadores.filter(pk=p.pk).exists() or (asignado(op, p) and op.permite_embarque_conductor)

def visible(op, p):
    return p.usuario.rol in VENTAS or asignado(op, p) or op.embarcadores.filter(pk=p.pk).exists()

def aviso_operacion(op, texto):
    for p in Perfil.objects.filter(Q(conductor_id__in=[op.salida.conductor_uno_id, op.salida.conductor_dos_id]) | Q(usuario__rol__in=VENTAS), activo=True).distinct():
        Aviso.objects.create(perfil=p, texto=texto[:500])

def disponibilidad(p, momento):
    regla = ReglaDescanso.objects.first()
    if not regla or not regla.activa:
        return {'permitido': True, 'mensaje': 'Regla de descanso de la empresa aún sin activar.'}
    d = Descanso.objects.filter(perfil=p, fin__isnull=True).order_by('-inicio').first()
    if not d:
        return {'permitido': False, 'mensaje': 'Falta registrar el inicio del descanso fuera del bus.'}
    habilitado = d.inicio + timedelta(hours=regla.horas)
    return {'permitido': momento >= habilitado, 'mensaje': f'Disponible desde {habilitado.astimezone(PERU):%d/%m %H:%M}.', 'desde': habilitado.isoformat()}

def datos_viaje(op, p, cache):
    s = op.salida
    return {'id': op.pk, 'fecha': str(s.fecha), 'hora': s.hora.strftime('%H:%M'), 'bus': s.bus,
        'ruta': f'{s.origen} → {s.destino}', 'estado': op.estado,
        'conductor_1': str(s.conductor_uno or ''), 'conductor_2': str(s.conductor_dos or ''),
        'pasajeros': s.pasajes_vendidos, 'conduce': op.conduciendo_id == p.pk,
        'relevo_pendiente': op.relevo_pendiente_id == p.pk, 'embarque': bool(p.usuario.rol in VENTAS or op.pk in cache['embarques'] or asignado(op,p) and op.permite_embarque_conductor),
        'asignado': bool(asignado(op, p)), 'disponibilidad': cache['disponibilidad'],
        'companero_perfil': next((cache['perfiles'].get(cid) for cid in [s.conductor_uno_id,s.conductor_dos_id] if cid != p.conductor_id),None),
        'salida_real': op.salida_real, 'llegada_real': op.llegada_real,
        'perfiles_conductores':[cache['perfiles'].get(s.conductor_uno_id),cache['perfiles'].get(s.conductor_dos_id)],
        'incidencias': cache['incidencias'].get(op.pk,[]),
        'puntos': cache['puntos'].get(op.pk,[])}

def snapshot(p):
    from .funciones import sincronizar_funcion
    sincronizar_funcion(p)
    from asistencia.models import TurnoHorario
    hoy = timezone.now().astimezone(PERU).date()
    inicio = hoy.replace(day=1)
    operaciones = Operacion.objects.select_related('salida__conductor_uno', 'salida__conductor_dos').filter(salida__fecha__gte=inicio-timedelta(days=7))
    if p.usuario.rol not in VENTAS:
        q = Q(embarcadores=p)
        if p.conductor_id:
            q |= Q(salida__conductor_uno_id=p.conductor_id) | Q(salida__conductor_dos_id=p.conductor_id)
        operaciones = operaciones.filter(q).distinct()
    operaciones=list(operaciones.order_by('salida__fecha','salida__hora')[:500])
    ids=[op.pk for op in operaciones]
    cache={'incidencias':{},'puntos':{},'embarques':set(Operacion.objects.filter(pk__in=ids,embarcadores=p).values_list('id',flat=True)),
           'perfiles':dict(Perfil.objects.filter(conductor__isnull=False,activo=True).values_list('conductor_id','pk')),'disponibilidad':disponibilidad(p,timezone.now())}
    for i in Incidencia.objects.filter(operacion_id__in=ids).values('id','operacion_id','tipo','descripcion','estado','monto'):
        cache['incidencias'].setdefault(i.pop('operacion_id'),[]).append(i)
    for oid,punto in Pasajero.objects.filter(operacion_id__in=ids).values_list('operacion_id','punto').distinct():
        cache['puntos'].setdefault(oid,[]).append(punto)
    marcas = list(Registro.objects.filter(perfil=p, jornada__gte=inicio).order_by('-recibido').values('id', 'tipo', 'recibido', 'jornada', 'estado', 'motivo'))
    solicitudes = Solicitud.objects.all() if p.usuario.rol in GESTION else Solicitud.objects.filter(perfil=p)
    jornadas = []
    if p.trabajador_id:
        from asistencia.models import ResumenAsistenciaDiaria, ProgramacionHorario
        jornadas = list(ResumenAsistenciaDiaria.objects.filter(trabajador=p.trabajador, fecha__gte=inicio,fecha__lte=hoy).values())
        horarios = [{'fecha': str(x.fecha), 'turno': str(x.turno)} for x in ProgramacionHorario.objects.filter(trabajador=p.trabajador, fecha__gte=hoy).select_related('turno')[:40]]
    else:
        horarios = []
    propios = Operacion.objects.filter(Q(salida__conductor_uno_id=p.conductor_id) | Q(salida__conductor_dos_id=p.conductor_id), estado='FINALIZADO', salida__anulado=False, salida__fecha__gte=inicio, salida__fecha__lte=hoy).exclude(salida__estado_operativo='CANCELADO') if p.conductor_id else Operacion.objects.none()
    trayectos = propios.count()
    from collections import Counter
    dias = Counter(propios.values_list('salida__fecha', flat=True))
    pagos = list(Pago.objects.filter(perfil=p, desde__gte=inicio).values('desde', 'hasta', 'monto', 'referencia'))
    resumen={'desde': str(inicio), 'trayectos_realizados': trayectos, 'vueltas': trayectos/2, 'estimado': trayectos*10,
             'HORA': sum(n==1 for n in dias.values()), 'X': sum(n==2 for n in dias.values()), 'XX': sum(n==3 for n in dias.values()),
             'pagado': str(sum((x['monto'] for x in pagos), Decimal(0)))} if p.conductor_id else {
             'desde':str(inicio),'jornadas':len(jornadas),'aprobadas':sum(x.get('estado_revision')=='APROBADO' for x in jornadas),
             **{campo:str(sum((Decimal(str(x.get(campo) or 0)) for x in jornadas),Decimal(0))) for campo in ['horas_trabajadas','horas_extras_25','horas_extras_35','horas_nocturnas']}}
    return {'perfil': {'id': p.pk, 'codigo': p.codigo, 'nombre': nombre(p), 'rol': p.usuario.rol, 'facial_requerido': p.requiere_rostro,
                      'area':'Conductores' if p.conductor_id else (p.trabajador.area if p.trabajador_id else ''),
                      'es_conductor':bool(p.conductor_id),'puede_ver_viajes':bool(p.conductor_id or p.usuario.rol in VENTAS or p.usuario.rol=='OPERADOR_EMBARQUE' or operaciones)},
        'turnos': list(TurnoHorario.objects.filter(activo=True).values('id','nombre')),
        'marcaciones': marcas, 'horarios': horarios, 'jornadas': jornadas,
        'solicitudes': list(solicitudes.order_by('-creado')[:100].values('id', 'perfil__codigo', 'tipo', 'desde', 'hasta', 'detalle', 'estado', 'respuesta')),
        'viajes': [datos_viaje(x, p, cache) for x in operaciones],
        'resumen': resumen,
        'comision_actual':Comision.objects.filter(perfil=p,desde__lte=timezone.now(),hasta__gte=timezone.now()).exists(),
        'ausencia_hoy':Solicitud.objects.filter(perfil=p,estado='APROBADO',tipo__in=['PERMISO','VACACIONES'],desde__lte=timezone.now().astimezone(PERU).date(),hasta__gte=timezone.now().astimezone(PERU).date()).exists(),
        'pagos': pagos, 'avisos': list(Aviso.objects.filter(perfil=p).order_by('-creado')[:50].values('id', 'texto', 'creado', 'leido')),
        'embarcadores':[{'id':x.pk,'nombre':nombre(x),'conductor':bool(x.conductor_id)} for x in Perfil.objects.filter(Q(usuario__rol='OPERADOR_EMBARQUE')|Q(conductor__isnull=False),activo=True).select_related('usuario','trabajador')] if p.usuario.rol in VENTAS else [],
        'conductores': list(Perfil.objects.filter(conductor__isnull=False, activo=True).values('id', 'codigo', 'conductor__nombre')) if p.usuario.rol in VENTAS else []}

def login(d, activar=False):
    codigo = str(d.get('codigo', '')).strip().upper()
    dispositivo = str(d.get('dispositivo', ''))
    exigir(10 <= len(dispositivo) <= 100, 'Identificador del dispositivo inválido.')
    # Contador persistente; evita depender de una caché local por proceso.
    contador, _ = IntentoAcceso.objects.select_for_update().get_or_create(clave=hash_token(codigo), defaults={'desde': timezone.now()})
    if timezone.now()-contador.desde > timedelta(minutes=15):
        contador.intentos, contador.desde = 0, timezone.now()
    exigir(contador.intentos < 8, 'Demasiados intentos. Espere 15 minutos.', 429)
    p = Perfil.objects.select_for_update(of=('self',)).select_related('usuario', 'trabajador').filter(codigo=codigo, activo=True, usuario__is_active=True, usuario__esta_activo=True).first()
    valido = False
    if p:
        if activar:
            valido = not p.activado and p.activacion_hasta and p.activacion_hasta > timezone.now() and check_password(str(d.get('activacion', '')), p.activacion_hash)
        else:
            valido = p.activado and p.usuario.check_password(str(d.get('password', '')))
    if not valido:
        contador.intentos += 1
        contador.save()
        # Retornar error, en lugar de lanzar: no revertir el contador en atomic.
        return JsonResponse({'ok': False, 'error': 'Código o credenciales incorrectos.'}, status=401)
    exigir(not p.dispositivo or p.dispositivo == dispositivo, 'Cuenta vinculada a otro teléfono. Solicite restablecer el dispositivo.', 403)
    if activar:
        validate_password(d.get('password', ''), p.usuario)
        p.usuario.set_password(d['password']); p.usuario.save(update_fields=['password'])
        p.activado, p.activacion_hash, p.activacion_hasta = True, '', None
    p.dispositivo = dispositivo; p.save()
    contador.intentos = 0; contador.save()
    token = secrets.token_urlsafe(48)
    Sesion.objects.create(perfil=p, token_hash=hash_token(token), vence=timezone.now()+timedelta(days=7))
    return {'token': token, **snapshot(p)}

def marcar(p, d):
    identificador = uuid.UUID(d['id'])
    previo = Registro.objects.filter(pk=identificador).first()
    if previo:
        exigir(previo.perfil_id == p.pk, 'Identificador ya utilizado.', 409)
        exigir(previo.tipo == d['tipo'], 'El reintento tiene otro contenido.', 409)
        return {'id': str(previo.pk), 'estado': previo.estado, 'mensaje': 'Marcación ya recibida.'}
    exigir(d['tipo'] in TIPOS, 'Tipo de marcación inválido.')
    ahora = timezone.now()
    captura = instante(d['capturada'])
    exigir(captura <= ahora+timedelta(minutes=2) and captura >= ahora-timedelta(days=7), 'Hora del teléfono inválida.')
    # Online uses the server clock; an offline capture is retained for daily review.
    momento_validacion = captura if d.get('offline') or (ahora-captura).total_seconds()>120 else ahora
    dia_validacion = momento_validacion.astimezone(PERU).date()
    exigir(not Solicitud.objects.filter(perfil=p,estado='APROBADO',tipo__in=['PERMISO','VACACIONES'],desde__lte=dia_validacion,hasta__gte=dia_validacion).exists(), 'Tiene permiso o vacaciones aprobados para esta fecha. No corresponde marcar asistencia.', 409)
    comision = Comision.objects.filter(perfil=p, desde__lte=momento_validacion, hasta__gte=momento_validacion).first()
    lat = lon = precision = None
    zona = None
    if not comision:
        lat, lon, precision = float(d['latitud']), float(d['longitud']), float(d['precision'])
        exigir(all(math.isfinite(x) for x in (lat, lon, precision)) and -90 <= lat <= 90 and -180 <= lon <= 180 and 0 < precision <= 100, 'Ubicación inválida o imprecisa.')
        gps = instante(d['gps_fecha'])
        exigir(abs((captura-gps).total_seconds()) <= 60, 'La ubicación debe ser reciente. Vuelva a obtenerla.')
        sede = p.trabajador.sede.strip() if p.trabajador_id else ''
        area = p.trabajador.area.strip() if p.trabajador_id else ''
        for z in Zona.objects.filter(activa=True).filter(Q(perfiles=p) | (Q(perfiles__isnull=True, sede__iexact=sede) & (Q(area='') | Q(area__iexact=area)))).distinct():
            a = math.sin(math.radians(lat-z.latitud)/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(z.latitud))*math.sin(math.radians(lon-z.longitud)/2)**2
            metros = 6371000*2*math.asin(min(1, math.sqrt(a)))
            if precision <= z.precision_maxima and metros+precision <= z.radio:
                zona = z; break
    exigir(zona or comision, 'No está dentro de una zona autorizada y no tiene una comisión vigente.', 422)
    exigir(not p.requiere_rostro or comision, 'La verificación facial todavía no está habilitada. Solicite una alternativa autorizada.', 422)
    offline = bool(d.get('offline')) or (ahora-captura).total_seconds() > 120
    momento = captura if offline else ahora
    ultimo = Registro.objects.filter(perfil=p).exclude(estado='RECHAZADO').order_by('-recibido').first()
    jornada = momento.astimezone(PERU).date()
    if ultimo and ultimo.tipo != 'SALIDA' and ultimo.jornada >= jornada-timedelta(days=1):
        jornada = ultimo.jornada
    if not offline:
        esperado = 'ENTRADA' if not ultimo or ultimo.tipo == 'SALIDA' else {'ENTRADA': 'SALIDA_REFRIGERIO', 'SALIDA_REFRIGERIO': 'RETORNO_REFRIGERIO', 'RETORNO_REFRIGERIO': 'SALIDA'}[ultimo.tipo]
        exigir(d['tipo'] == esperado or (ultimo and ultimo.tipo == 'ENTRADA' and d['tipo'] == 'SALIDA'), f'Corresponde marcar {esperado}.', 409)
    r = Registro.objects.create(id=identificador, perfil=p, tipo=d['tipo'], fecha_dispositivo=captura, jornada=jornada,
        latitud=lat, longitud=lon, precision=precision, zona=zona, comision=comision,
        estado='POR_REVISAR' if offline else 'REGISTRADO', motivo='Hora del teléfono; requiere revisión.' if offline else '')
    if not offline:
        publicar_marca(r, momento)
    else:
        from asistencia.models import ResumenAsistenciaDiaria
        exigir(p.trabajador_id,'Vincule primero la ficha de personal.')
        ResumenAsistenciaDiaria.objects.get_or_create(trabajador=p.trabajador,fecha=jornada,defaults={'estado':'POR_REVISAR'})
    return {'id': str(r.pk), 'estado': r.estado, 'mensaje': 'Marcación recibida; pendiente de aprobación contable.'}

def publicar_marca(r, momento):
    from asistencia.models import IdentidadBiometrica, MarcacionBiometrica
    p = r.perfil
    exigir(p.trabajador_id, 'Falta vincular la ficha del trabajador.', 422)
    t = p.trabajador
    identidad, _ = IdentidadBiometrica.objects.get_or_create(sede=t.sede, equipo='APP', codigo=p.codigo, defaults={'trabajador': t, 'usuario': p.usuario, 'nombre': t.nombre_completo})
    r.marca = MarcacionBiometrica.objects.create(usuario=p.usuario, dni=t.dni, nombre_empleado=t.nombre_completo,
        identidad_biometrica=identidad, fecha_hora=momento, tipo_evento=r.tipo, origen='APP_MOVIL_GPS',
        latitud=r.latitud, longitud=r.longitud, es_valida=True, huella_importacion=hash_token('APP:'+str(r.pk)))
    r.save(update_fields=['marca'])
    from asistencia.services.transferencia import pasar_a_asistencia
    pasar_a_asistencia([t.pk], r.jornada, r.jornada, p.usuario)

def solicitud(p, d):
    tipo = d['tipo']
    exigir(tipo in ['PERMISO', 'VACACIONES', 'CAMBIO_HORARIO', 'CORRECCION'], 'Solicitud inválida.')
    desde, hasta = fecha(d['desde']), fecha(d['hasta'])
    exigir(desde <= hasta and (hasta-desde).days <= 366, 'Rango de fechas inválido.')
    detalle = str(d.get('detalle', '')).strip()
    exigir(5 <= len(detalle) <= 2000, 'Explique la solicitud (5 a 2000 caracteres).')
    exigir(tipo == 'CORRECCION' or d.get('emergencia') or desde > timezone.now().astimezone(PERU).date(), 'Debe solicitarlo como máximo el día anterior; explique si es una emergencia.')
    datos=d.get('datos',{})
    exigir(isinstance(datos,dict),'Revise los datos de la solicitud.')
    if tipo=='CAMBIO_HORARIO':
        from asistencia.models import TurnoHorario
        exigir(str(datos.get('turno','')).isdigit() and TurnoHorario.objects.filter(pk=datos.get('turno'),activo=True).exists(),'Seleccione el turno solicitado.')
    s = Solicitud.objects.create(perfil=p, tipo=tipo, desde=desde, hasta=hasta, detalle=detalle, emergencia=bool(d.get('emergencia')), datos=datos)
    for gestor in Perfil.objects.filter(usuario__rol__in=GESTION, activo=True):
        Aviso.objects.create(perfil=gestor, texto=f'Solicitud {s.pk}: {p.codigo}, {tipo}.')
    return {'mensaje': 'Solicitud enviada a revisión.', 'id': s.pk}

def evento(p, d):
    op = Operacion.objects.select_for_update().select_related('salida').get(pk=d['viaje'])
    exigir(asignado(op, p), 'No está asignado a este viaje.', 403)
    eid = uuid.UUID(d['id'])
    anterior = EventoViaje.objects.filter(pk=eid).first()
    if anterior:
        exigir(anterior.perfil_id == p.pk and anterior.operacion_id == op.pk and anterior.tipo == d['tipo'], 'Evento en conflicto.', 409)
        return {'mensaje': 'Evento ya registrado.'}
    tipo, ahora = d['tipo'], timezone.now()
    exigir(not d.get('offline'), 'Las salidas, relevos y llegadas requieren conexión. Informe una omisión para revisión.')
    if tipo == 'INICIAR':
        exigir(op.estado == 'PROGRAMADO' and not op.salida.anulado and op.salida.estado_operativo != 'CANCELADO', 'El viaje no está disponible para iniciar.', 409)
        exigir(op.salida.conductor_uno_id and op.salida.conductor_dos_id and op.salida.conductor_uno_id != op.salida.conductor_dos_id, 'Complete los dos conductores antes de iniciar.')
        programada = timezone.make_aware(datetime.combine(op.salida.fecha,op.salida.hora),PERU)
        exigir(abs((ahora-programada).total_seconds())<=24*3600,'La salida programada no corresponde a esta fecha. Ventas debe corregir la asignación.',409)
        perfiles = list(Perfil.objects.filter(conductor_id__in=[op.salida.conductor_uno_id,op.salida.conductor_dos_id],activo=True,usuario__is_active=True))
        exigir(len(perfiles)==2,'Falta habilitar la cuenta de uno de los dos conductores.',409)
        from conductores.models import SituacionConductor
        exigir(not SituacionConductor.objects.filter(conductor_id__in=[op.salida.conductor_uno_id,op.salida.conductor_dos_id],activa=True,inicio__lte=op.salida.fecha,fin__gte=op.salida.fecha).exists(),'Un conductor tiene descanso, vacaciones u otra situación registrada. Ventas debe reemplazarlo o corregir la situación.',409)
        otros = Operacion.objects.filter(estado='EN_CURSO').exclude(pk=op.pk).filter(Q(salida__conductor_uno_id__in=[op.salida.conductor_uno_id, op.salida.conductor_dos_id]) | Q(salida__conductor_dos_id__in=[op.salida.conductor_uno_id, op.salida.conductor_dos_id]))
        exigir(not otros.exists(), 'Un conductor tiene otro viaje en curso.', 409)
        for perfil in perfiles:
            disponible = disponibilidad(perfil, ahora)
            exigir(disponible['permitido'], disponible['mensaje'], 409)
            Descanso.objects.filter(perfil=perfil, fin__isnull=True).update(fin=ahora)
        op.estado, op.salida_real, op.conduciendo = 'EN_CURSO', ahora, p
    elif tipo == 'SOLICITAR_RELEVO':
        exigir(op.estado == 'EN_CURSO' and op.conduciendo_id == p.pk, 'Solo quien conduce solicita el relevo.', 409)
        relevo = Perfil.objects.get(pk=d['relevo'])
        exigir(asignado(op, relevo) and relevo.pk != p.pk, 'Relevo inválido.')
        op.relevo_pendiente = relevo
    elif tipo == 'ACEPTAR_RELEVO':
        exigir(op.estado == 'EN_CURSO' and op.relevo_pendiente_id == p.pk, 'No tiene un relevo pendiente.', 409)
        op.conduciendo, op.relevo_pendiente = p, None
    elif tipo == 'LLEGADA':
        exigir(op.estado == 'EN_CURSO', 'El viaje no está en curso.', 409)
        op.estado, op.llegada_real, op.conduciendo, op.relevo_pendiente = 'FINALIZADO', ahora, None, None
        op.salida.estado_operativo='REALIZADO';op.salida.save(update_fields=['estado_operativo'])
    elif tipo == 'DESCANSO':
        exigir(op.estado == 'FINALIZADO', 'Registre primero la llegada.', 409)
        exigir(not Descanso.objects.filter(perfil=p, fin__isnull=True).exists(), 'Ya tiene un descanso abierto.', 409)
        Descanso.objects.create(perfil=p, operacion=op, inicio=ahora)
    else:
        raise Problema('Acción no válida.')
    op.save()
    EventoViaje.objects.create(id=eid, operacion=op, perfil=p, tipo=tipo, datos={'relevo': d.get('relevo')})
    aviso_operacion(op, f'{op.salida.origen} → {op.salida.destino}: {tipo}.')
    return {'mensaje': 'Viaje actualizado.'}

@csrf_exempt
def api(request, accion):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST.'}, status=405)
    try:
        exigir(len(request.body) <= 8_000_000, 'Archivo demasiado grande.', 413)
        d = json.loads(request.body or '{}')
        exigir(isinstance(d, dict), 'JSON inválido.')
        with transaction.atomic():
            if accion in ('verificar_activacion','establecer_password'):
                from .activacion import ejecutar_activacion
                resultado=ejecutar_activacion(accion,d,request.META.get('REMOTE_ADDR',''))
            elif accion in ('login', 'activar'):
                resultado = login(d, accion == 'activar')
            else:
                token = request.headers.get('Authorization', '').removeprefix('Bearer ')
                exigir(request.headers.get('Authorization','').startswith('Bearer '),'Se requiere un token de acceso.',401)
                sesion = Sesion.objects.select_related('perfil__usuario', 'perfil__trabajador').filter(token_hash=hash_token(token), activa=True, vence__gt=timezone.now(), perfil__activo=True, perfil__usuario__is_active=True, perfil__usuario__esta_activo=True).first()
                exigir(sesion, 'Inicie sesión nuevamente.', 401)
                p = Perfil.objects.select_for_update(of=('self',)).select_related('usuario', 'trabajador').get(pk=sesion.perfil_id)
                resultado = ejecutar(accion, p, d, sesion)
            if isinstance(resultado, HttpResponse):
                return resultado
            return JsonResponse({'ok': True, **resultado}, json_dumps_params={'ensure_ascii': False})
    except Problema as e:
        return JsonResponse({'ok': False, 'error': e.mensaje}, status=e.status)
    except ValidationError as e:
        return JsonResponse({'ok': False, 'error': ' '.join(e.messages)}, status=422)
    except IntegrityError:
        return JsonResponse({'ok':False,'error':'Otro dispositivo actualizó el registro. Sincronice antes de reintentar.'},status=409)
    except (ValueError, TypeError, KeyError, OverflowError, InvalidOperation):
        return JsonResponse({'ok': False, 'error': 'Revise los datos enviados.'}, status=400)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Registro no encontrado.'}, status=404)

def ejecutar(accion, p, d, sesion):
    if accion == 'inicio': return snapshot(p)
    if accion == 'logout':
        sesion.activa = False; sesion.save(); return {'mensaje': 'Sesión cerrada.'}
    if accion == 'marcar': return marcar(p, d)
    if accion == 'solicitud': return solicitud(p, d)
    if accion == 'evento': return evento(p, d)
    if accion == 'avisos':
        Aviso.objects.filter(perfil=p, pk__in=d.get('ids', [])).update(leido=True)
        return {'mensaje': 'Notificaciones leídas.'}
    if accion in ('pasajeros', 'embarcar', 'manifiesto'):
        op = Operacion.objects.select_for_update().select_related('salida').get(pk=d['viaje'])
        exigir(embarque(op, p), 'No está autorizado al embarque de este viaje.', 403)
        if accion == 'pasajeros':
            return {'pasajeros': list(op.pasajeros.order_by('piso', 'asiento', 'pk').values('id', 'referencia', 'nombre', 'documento', 'edad', 'piso', 'asiento', 'origen', 'destino', 'punto', 'estado'))}
        if accion == 'manifiesto':
            import csv, io
            buf = io.StringIO(); w = csv.writer(buf)
            w.writerow(['MANIFIESTO INTERNO - No acredita transmisión oficial al MTC'])
            w.writerow(['Piso', 'Asiento', 'Pasajero', 'Documento', 'Origen', 'Destino', 'Punto', 'Estado'])
            for x in op.pasajeros.order_by('piso', 'asiento'):
                w.writerow([x.piso, x.asiento, *[("'"+v if str(v).lstrip().startswith(('=', '+', '-', '@')) else v) for v in [x.nombre, x.documento, x.origen, x.destino, x.punto, x.estado]]])
            return {'archivo': buf.getvalue(), 'nombre': f'manifiesto_interno_{op.pk}.csv'}
        pasajero = Pasajero.objects.select_for_update().get(pk=d['pasajero'], operacion=op)
        eid = uuid.UUID(d['id'])
        if pasajero.sincronizacion_id == eid:
            return {'mensaje': 'Verificación ya recibida.'}
        exigir(pasajero.estado == d['anterior'], 'El asiento cambió. Actualice y revise.', 409)
        exigir(d['estado'] in ['EMBARCADO', 'NO_PRESENTADO', 'DESEMBARCADO'], 'Estado inválido.')
        exigir(d['estado'] != 'EMBARCADO' or d.get('identidad_verificada') is True, 'Confirme documento y boleto antes de embarcar.')
        exigir(pasajero.estado not in ['CANCELADO', 'DESEMBARCADO'], 'Reserva cerrada.', 409)
        exigir(d['estado'] != 'DESEMBARCADO' or pasajero.estado == 'EMBARCADO', 'El pasajero no está embarcado.')
        if d['estado'] == 'EMBARCADO':
            exigir(not op.pasajeros.exclude(pk=pasajero.pk).filter(piso=pasajero.piso, asiento=pasajero.asiento, estado='EMBARCADO').exists(), 'Este asiento sigue ocupado.', 409)
        pasajero.estado, pasajero.verificado_por, pasajero.verificado_el, pasajero.sincronizacion_id = d['estado'], p, timezone.now(), eid
        pasajero.save()
        Auditoria.objects.create(actor=p.usuario, accion='embarque', detalle={'pasajero': pasajero.pk, 'estado': pasajero.estado})
        return {'mensaje': 'Verificación guardada.'}
    if accion == 'incidencia':
        op = Operacion.objects.select_related('salida').get(pk=d['viaje'])
        exigir(visible(op, p), 'Viaje no autorizado.', 403)
        exigir(5 <= len(d.get('descripcion', '')) <= 2000, 'Describa la incidencia.')
        monto = Decimal(str(d['monto'])) if d.get('monto') else None
        exigir(monto is None or monto.is_finite() and 0 <= monto <= 99999999, 'Importe inválido.')
        i = Incidencia.objects.create(operacion=op, perfil=p, tipo=str(d['tipo'])[:40], descripcion=d['descripcion'], monto=monto)
        aviso_operacion(op, f'Incidencia {i.pk}: {i.tipo}. {i.descripcion[:200]}')
        return {'mensaje': 'Incidencia reportada.'}
    from .gestion import gestionar
    return gestionar(accion, p, d)

