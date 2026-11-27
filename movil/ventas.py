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
    if request.user.rol not in VENTAS or request.user.rol == 'CONTADORA':
        return HttpResponseForbidden('Esta sección corresponde a Ventas / Boletería.')
    if request.method=='POST':
        try:
            with transaction.atomic():
                perfil,_=Perfil.objects.get_or_create(usuario=request.user)
                accion=request.POST.get('accion')
                datos=dict(request.POST.items())
                if accion=='descartar_comparacion':
                    from .revision_itinerario import descartar
                    descartar(request.session)
                    return redirect('/movil/ventas/')
                elif accion=='validar_comparacion':
                    from .revision_itinerario import validar
                    actualizadas,nuevas=validar(request.session,request.POST,request.user)
                    messages.success(request,f'{actualizadas} salidas actualizadas; {nuevas} nuevas. Revisión validada.')
                    return redirect('/movil/ventas/')
                elif accion=='importar_itinerario':
                    request.session.pop('comparacion_itinerario',None)
                    from .revision_itinerario import descartar
                    descartar(request.session)
                    archivo=request.FILES.get('archivo')
                    if not archivo or archivo.size>6_000_000:raise Problema('Seleccione un Excel de hasta 6 MB.')
                    contenido=archivo.read()
                    from django.core.files.base import ContentFile
                    from conductores.parser import extraer
                    from .comparacion_itinerarios import comparar_filas
                    filas,errores=extraer(ContentFile(contenido,name=archivo.name))
                    if errores or not filas:raise Problema('Reporte inválido: '+'; '.join(map(str,errores[:5])))
                    if len(filas)>10000:raise Problema('Máximo 10000 filas por archivo.')
                    comparacion=comparar_filas(filas)
                    if any(c['estado'] in ('CAMBIO','CONFLICTO','PENDIENTE') for c in comparacion):
                        from .revision_itinerario import preparar
                        preparar(request.session,archivo.name,filas,comparacion,contenido)
                        return redirect('/movil/ventas/')
                    datos={'nombre':archivo.name,'contenido':base64.b64encode(contenido).decode()}
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
            if request.POST.get('accion')=='validar_comparacion' and request.session.get('revision_itinerario'):
                revision=request.session['revision_itinerario']
                for cambio in revision['cambios']:
                    for diferencia in cambio['diferencias']:
                        if diferencia.get('codigo'):
                            nombre=f"c_{cambio['fila']}_{diferencia['codigo']}"
                            diferencia['valor']=request.POST.get(nombre,diferencia['valor'])[:180]
                request.session['revision_itinerario']=revision
            messages.error(request,getattr(e,'mensaje',str(e)))
        url='/movil/ventas/'
        if request.POST.get('viaje','').isdigit():url+='?viaje='+request.POST['viaje']
        return redirect(url)
    from .registro_ventas import contexto_registro
    import time
    if request.session.get('revision_itinerario',{}).get('vence',float('inf'))<time.time():
        from .revision_itinerario import descartar
        descartar(request.session)
    context=contexto_registro(request)
    context.update({'revision_itinerario':request.session.get('revision_itinerario')})
    return render(request,'movil/ventas.html',context)
