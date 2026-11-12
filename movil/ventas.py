import base64
from datetime import timedelta, date
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError,ObjectDoesNotExist
from django.http import HttpResponseForbidden
from django.shortcuts import render,redirect
from django.utils import timezone
from .models import Perfil,Operacion
from .views import VENTAS,Problema
from .gestion import gestionar

@login_required
def ventas(request):
    if request.user.rol not in VENTAS:
        return HttpResponseForbidden('Esta sección corresponde a Ventas / Boletería.')
    if request.method=='POST':
        try:
            with transaction.atomic():
                perfil,_=Perfil.objects.get_or_create(usuario=request.user)
                accion=request.POST.get('accion')
                datos=dict(request.POST.items())
                if accion=='importar_itinerario':
                    archivo=request.FILES.get('archivo')
                    if not archivo or archivo.size>6_000_000:raise Problema('Seleccione un Excel de hasta 6 MB.')
                    datos={'nombre':archivo.name,'contenido':base64.b64encode(archivo.read()).decode()}
                elif accion=='importar_pasajeros':
                    archivo=request.FILES.get('archivo')
                    if not archivo or archivo.size>1_000_000:raise Problema('Seleccione un CSV de hasta 1 MB.')
                    datos={'viaje':request.POST['viaje'],'csv':archivo.read().decode('utf-8-sig')}
                elif accion=='asignar_embarque':
                    datos['conductores']=request.POST.get('conductores')=='on'
                elif accion=='asignar':
                    datos['embarque_conductor']=request.POST.get('embarque_conductor')=='on'
                    datos['fin_previsto']=request.POST['fin_previsto']+'-05:00'
                elif accion=='resolver_incidencia':
                    pass
                else:raise Problema('Acción no permitida en Ventas.')
                resultado=gestionar(accion,perfil,datos)
                messages.success(request,resultado['mensaje'])
        except (Problema,ValidationError,ValueError,KeyError,ObjectDoesNotExist) as e:
            messages.error(request,getattr(e,'mensaje',str(e)))
        url='/movil/ventas/'
        if request.POST.get('viaje','').isdigit():url+='?viaje='+request.POST['viaje']
        return redirect(url)
    try:
        desde=date.fromisoformat(request.GET.get('desde',''))
        hasta=date.fromisoformat(request.GET.get('hasta',''))
    except ValueError:
        desde=timezone.localdate().replace(day=1);hasta=desde+timedelta(days=60)
    operaciones=Operacion.objects.filter(salida__fecha__range=(desde,hasta)).select_related('salida__conductor_uno','salida__conductor_dos').order_by('salida__fecha','salida__hora')[:200]
    seleccionada=Operacion.objects.select_related('salida__conductor_uno','salida__conductor_dos').filter(pk=request.GET.get('viaje')).first() if request.GET.get('viaje','').isdigit() else None
    from .models import Incidencia
    return render(request,'movil/ventas.html',{'operaciones':operaciones,'seleccionada':seleccionada,'desde':desde,'hasta':hasta,'incidencias':Incidencia.objects.filter(operacion=seleccionada) if seleccionada else []})
