import secrets
from datetime import timedelta
from decimal import Decimal
from decimal import InvalidOperation
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.shortcuts import render, redirect
from django.utils import timezone
from asistencia.models import Trabajador
from conductores.models import Conductor
from .models import Perfil, Zona, Comision, Operacion, Registro, Solicitud, Pago, Auditoria, ReglaDescanso
from .views import GESTION, exigir, Problema, instante
from .gestion import gestionar

@login_required
@never_cache
def panel(request):
    if request.user.rol not in GESTION:
        return HttpResponseForbidden('Solo administración y contabilidad pueden gestionar la aplicación.')
    activacion=None
    activacion_perfil=None
    activacion_codigo=None
    if request.method=='POST':
        try:
            with transaction.atomic():
                accion=request.POST.get('accion')
                actor,_=Perfil.objects.get_or_create(usuario=request.user)
                if accion=='habilitar':
                    from .cuentas import cuenta_para_ficha, cuenta_para_conductor
                    persona=request.POST.get('persona','')
                    if persona:
                        tipo,_,pk=persona.partition(':')
                        exigir(tipo in ('trabajador','conductor') and pk.isdigit(),'Seleccione una sugerencia válida.')
                    else:
                        tipo,pk='trabajador',request.POST.get('trabajador','')
                    if tipo=='conductor':
                        usuario,conductor,t=cuenta_para_conductor(pk,request.POST.get('dni_conductor','').strip(),request.POST.get('sede_conductor',''),request.user)
                    else:
                        t=cuenta_para_ficha(pk,request.user)
                        usuario,conductor=t.usuario,Conductor.objects.filter(trabajador=t).first()
                    from .funciones import funcion_por_area
                    inferida=funcion_por_area(t.area if t else '',bool(conductor))
                    funcion=inferida or request.POST.get('funcion_app','')
                    if funcion and usuario.rol not in GESTION and not usuario.is_staff and not usuario.is_superuser:
                        exigir(funcion in ['CONDUCTOR','ADMINISTRATIVO','BOLETERIA','OPERADOR_EMBARQUE'],'Función de app inválida.')
                        exigir(not conductor or funcion=='CONDUCTOR','El conductor conserva su función.')
                        exigir(usuario.rol not in GESTION and not usuario.is_staff and not usuario.is_superuser,'Esta cuenta administrativa conserva sus permisos actuales.')
                        usuario.rol=funcion;usuario.save(update_fields=['rol'])
                    p,_=Perfil.objects.get_or_create(usuario=usuario,defaults={'trabajador':t,'conductor':conductor})
                    p.trabajador=t
                    p.conductor=conductor
                    from .activacion import nuevo_codigo
                    codigo=nuevo_codigo(p)
                    p.activacion_hash=make_password(codigo);p.activacion_hasta=timezone.now()+timedelta(hours=24)
                    p.activado=False;p.activo=True;p.dispositivo='';p.full_clean(exclude=['codigo']);p.save()
                    p.sesion_set.update(activa=False)
                    activacion=f'{p.codigo} · Activación: {codigo} (un uso, 24 horas)'
                    activacion_perfil=p.pk
                    activacion_codigo=codigo
                    Auditoria.objects.create(actor=request.user,accion='habilitar_app',detalle={'perfil':p.pk})
                elif accion in ('zona','editar_zona'):
                    personal=None
                    if request.POST.get('alcance')=='trabajador':
                        personal=Perfil.objects.select_related('trabajador').get(pk=request.POST['perfil'],activo=True,conductor__isnull=True,trabajador__isnull=False)
                    z=Zona(nombre=request.POST['nombre'],sede=personal.trabajador.sede if personal else request.POST['sede'],latitud=float(request.POST['latitud']),longitud=float(request.POST['longitud']),radio=int(request.POST['radio']),precision_maxima=50)
                    exigir(-90<=z.latitud<=90 and -180<=z.longitud<=180 and 20<=z.radio<=2000,'Revise coordenadas y radio (20 a 2000 metros).')
                    z.area=request.POST.get('area','').strip() if request.POST.get('alcance')=='area' else ''
                    exigir(request.POST.get('alcance')!='area' or bool(z.area),'Indique el área de trabajo.')
                    if accion=='editar_zona':
                        anterior=Zona.objects.get(pk=request.POST['zona'])
                        for campo in ('nombre','sede','area','latitud','longitud','radio'):
                            setattr(anterior,campo,getattr(z,campo))
                        z=anterior
                    z.full_clean();z.save()
                    z.perfiles.clear()
                    if personal:z.perfiles.add(personal)
                elif accion in ('desactivar_zona','activar_zona'):
                    Zona.objects.filter(pk=request.POST['zona']).update(activa=accion=='activar_zona')
                elif accion=='eliminar_zona':
                    z=Zona.objects.get(pk=request.POST['zona'])
                    exigir(not z.registro_set.exists(),'Esta zona tiene marcaciones: desactívela para conservar su historial.')
                    z.delete()
                elif accion=='comision':
                    c=Comision(perfil_id=int(request.POST['perfil']),motivo=request.POST['motivo'],desde=instante(request.POST['desde']+'-05:00'),hasta=instante(request.POST['hasta']+'-05:00'),autorizada_por=request.user,sin_rostro=True)
                    exigir(c.desde<c.hasta and bool(c.motivo.strip()),'Indique motivo y período válido.');c.full_clean();c.save()
                elif accion=='pago':
                    referencia=request.POST.get('id_pago') or request.POST.get('referencia') or secrets.token_hex(16)
                    exigir(not Pago.objects.filter(perfil_id=request.POST['perfil'],referencia=referencia).exists(),'Este pago ya está registrado. Actualice la página antes de registrar otro.')
                    pago=Pago(perfil_id=int(request.POST['perfil']),desde=request.POST['desde'],hasta=request.POST['hasta'],monto=Decimal(request.POST['monto']),referencia=referencia,registrado_por=request.user)
                    pago.full_clean();exigir(str(pago.desde)<=str(pago.hasta) and pago.monto>0,'Revise período e importe.');pago.save()
                elif accion=='embarque':
                    raise Problema('Asigne el responsable desde Ventas y embarque.')
                elif accion=='regla':
                    regla,_=ReglaDescanso.objects.get_or_create(pk=1)
                    regla.horas=int(request.POST['horas']);exigir(1<=regla.horas<=24,'Horas entre 1 y 24.')
                    regla.activa=request.POST.get('confirmado')=='on';regla.save()
                elif accion=='revisar_solicitud':
                    gestionar(accion,actor,{'id':int(request.POST['id']),'aprobar':request.POST['decision']=='aprobar','respuesta':request.POST.get('respuesta',''),'turno':request.POST.get('turno')})
                elif accion=='revisar_marca':
                    raise Problema('Las marcaciones se revisan únicamente en el detalle diario de Asistencia.')
                else: raise Problema('Acción inválida.')
                Auditoria.objects.create(actor=request.user,accion='panel_'+str(accion),detalle={})
                messages.success(request,'Configuración guardada.')
        except (Problema,ValidationError,ValueError,KeyError,ObjectDoesNotExist,InvalidOperation,ProtectedError) as e:
            messages.error(request,getattr(e,'mensaje',str(e)))
    from asistencia.models import TurnoHorario
    return render(request,'movil/panel.html',{'areas':Trabajador.objects.exclude(area='').order_by('area').values_list('area',flat=True).distinct(),'sedes':Trabajador.objects.exclude(sede='').order_by('sede').values_list('sede',flat=True).distinct(),'id_pago':secrets.token_hex(16),'trabajador_seleccionado': int(request.POST['trabajador']) if request.method=='POST' and str(request.POST.get('trabajador','')).isdigit() else None,'activacion':activacion,'activacion_perfil':activacion_perfil,'activacion_codigo':activacion_codigo,'perfiles':Perfil.objects.filter(Q(trabajador__isnull=False)|Q(conductor__isnull=False)).exclude(Q(usuario__rol__in=GESTION)&(Q(trabajador__area='')|Q(trabajador__isnull=True))).select_related('trabajador','usuario','conductor'),'trabajadores':Trabajador.objects.select_related('usuario').all(),'zonas':Zona.objects.all(),'solicitudes':Solicitud.objects.filter(estado='PENDIENTE').select_related('perfil'),'registros':Registro.objects.filter(estado='POR_REVISAR').select_related('perfil'),'operaciones':Operacion.objects.filter(estado='PROGRAMADO').select_related('salida')[:100],'turnos':TurnoHorario.objects.all(),'regla':ReglaDescanso.objects.first()})

@login_required
@require_GET
@never_cache
def estados_acceso(request):
    if request.user.rol not in GESTION:
        return HttpResponseForbidden('No tiene permiso para consultar accesos.')
    return JsonResponse({'perfiles':[{'id':p.pk,'estado':p.estado_acceso} for p in Perfil.objects.select_related('usuario')]})

