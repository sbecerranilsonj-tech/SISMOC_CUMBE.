from datetime import date, datetime, timedelta
from io import BytesIO
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponse,HttpResponseForbidden
from django.shortcuts import redirect,render
from django.utils import timezone
from conductores.models import Salida
from .models import Operacion,Perfil,Auditoria
from .views import PERU,VENTAS,Problema,exigir,aviso_operacion
from .pasajeros_excel import asientos_distribucion,importar_pasajeros_excel


@login_required
def buses(request):
    if request.user.rol not in VENTAS or request.user.rol=='CONTADORA':return HttpResponseForbidden('Esta sección corresponde a Boletería.')
    if request.GET.get('plantilla')=='1':
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill,Font
        wb=Workbook();ws=wb.active;ws.title='Pasajeros'
        ws.append(['Boleto','Pasajero','Documento','Piso','Asiento','Origen','Destino','Punto de embarque','Punto de desembarque'])
        for c in ws[1]:c.fill=PatternFill('solid',fgColor='173B35');c.font=Font(color='FFFFFF',bold=True);ws.column_dimensions[c.column_letter].width=24
        ws.column_dimensions['B'].width=38;ws.column_dimensions['C'].number_format='@';ws.freeze_panes='A2'
        buffer=BytesIO();wb.save(buffer)
        response=HttpResponse(buffer.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');response['Content-Disposition']='attachment; filename="plantilla_pasajeros.xlsx"';return response
    try:
        desde=date.fromisoformat(request.GET.get('desde',''));hasta=date.fromisoformat(request.GET.get('hasta',''))
        exigir(desde<=hasta and (hasta-desde).days<=366,'Seleccione un período de hasta un año.')
    except (ValueError,Problema):
        desde=timezone.localdate().replace(day=1)
        hasta=(desde.replace(year=desde.year+1,month=1)
               if desde.month==12 else desde.replace(month=desde.month+1))-timedelta(days=1)
    if request.method=='POST':
        seleccion=request.POST.get('salida','')
        try:
            with transaction.atomic():
                if request.POST.get('accion') == 'programar':
                    from .programacion_manual import programar
                    op, publicada, motivo = programar(request.POST, request.user)
                    if publicada:
                        messages.success(request, 'Viaje programado. La asignación ya puede aparecer en la app de ambos conductores.')
                    else:
                        messages.warning(request, 'Viaje conservado: ' + motivo +
                                         ' Cambie de conductor o programe cuando se cumplan las 8 horas desde su llegada.')
                    return redirect('/movil/buses/?desde='+str(op.salida.fecha)+'&hasta='+str(op.salida.fecha))
                if request.POST.get('accion') == 'editar':
                    from .programacion_manual import editar
                    op, publicada, motivo = editar(request.POST, seleccion, request.user)
                    if publicada:
                        messages.success(request, 'Viaje actualizado. La asignación sigue visible en la app de ambos conductores.')
                    else:
                        messages.warning(request, 'Viaje actualizado, pendiente de revisión: ' + motivo +
                                         ' Se conservaron pasajeros, distribución y responsable de embarque.')
                    return redirect('/movil/buses/?desde=' + str(op.salida.fecha) + '&hasta=' + str(op.salida.fecha) + '&salida=' + str(op.salida.pk))
                if request.POST.get('accion') == 'publicar_automatico':
                    from .programacion_manual import publicar_automatico
                    from .programacion_manual import Problema as _Problema
                    try:
                        op = publicar_automatico(seleccion, request.user)
                    except _Problema as e:
                        messages.error(request, e.mensaje)
                        return redirect('/movil/buses/?desde='+str(desde)+'&hasta='+str(hasta)+'&salida='+str(seleccion)+'&descanso_revisado=1')
                    messages.success(request, 'Conductores aptos: descanso comprobado desde la llegada. La asignación aparece en la app.')
                    return redirect('/movil/buses/?desde='+str(op.salida.fecha)+'&hasta='+str(op.salida.fecha)+'&salida='+str(op.salida.pk))
                if request.POST.get('accion') == 'publicar_programacion':
                    from .programacion_manual import publicar_pendiente
                    op = publicar_pendiente(seleccion, request.user)
                    messages.success(request, 'Descanso verificado y autorización auditada. La asignación puede aparecer en la app.')
                    return redirect('/movil/buses/?desde='+str(op.salida.fecha)+'&hasta='+str(op.salida.fecha))
                s=Salida.objects.select_for_update().get(pk=seleccion,importacion__estado='VALIDADO')
                exigir(not s.anulado and s.estado_operativo!='CANCELADO','La salida está cancelada.')
                op,_=Operacion.objects.get_or_create(salida=s)
                accion=request.POST.get('accion')
                if accion=='distribucion':
                    n1,n2=int(request.POST['piso1']),int(request.POST['piso2'])
                    exigir(op.estado=='PROGRAMADO' and 1<=n1<=100 and 0<=n2<=100,'Revise la cantidad de asientos por piso.')
                    exigir(s.comercial['capacidad'] is None or n1+n2==s.comercial['capacidad'],'La suma por pisos debe coincidir con la capacidad del itinerario.')
                    modo=request.POST['numeracion'];exigir(modo in ('continua','por_piso'),'Numeración inválida.')
                    config={'piso1':n1,'piso2':n2,'numeracion':modo,'confirmada':True}
                    exigir(all((p.piso,p.asiento) in asientos_distribucion(config) for p in op.pasajeros.all()),'La distribución dejaría pasajeros fuera del bus.')
                    op.distribucion_asientos=config;op.save(update_fields=['distribucion_asientos'])
                    Auditoria.objects.create(actor=request.user,accion='distribucion_bus',detalle={'viaje':op.pk,**config})
                    messages.success(request,'Distribución del bus guardada.')
                elif accion=='pasajeros_excel':
                    archivo=request.FILES.get('archivo');exigir(archivo,'Seleccione el Excel de pasajeros.')
                    nuevos,actualizados=importar_pasajeros_excel(op.pk,archivo,request.user)
                    messages.success(request,f'{nuevos} pasajeros añadidos; {actualizados} actualizados.')
                elif accion=='puntos':
                    p=op.pasajeros.select_for_update().get(pk=request.POST['pasajero'])
                    exigir(op.estado=='PROGRAMADO' and p.estado=='PENDIENTE','El viaje o pasajero ya fue verificado. Se conservan sus datos.')
                    p.punto=request.POST['punto'].strip();p.punto_desembarque=request.POST['punto_desembarque'].strip()
                    exigir(p.punto and p.punto_desembarque,'Complete ambos puntos.');p.full_clean();p.save(update_fields=['punto','punto_desembarque'])
                    aviso_operacion(op,f'Puntos actualizados para el asiento {p.asiento}.')
                    Auditoria.objects.create(actor=request.user,accion='puntos_pasajero',detalle={'pasajero':p.pk,'embarque':p.punto,'desembarque':p.punto_desembarque})
                    messages.success(request,'Puntos de embarque y desembarque guardados.')
                elif accion=='embarcador':
                    exigir(op.estado=='PROGRAMADO','El viaje ya inició.')
                    perfil=Perfil.objects.get(pk=request.POST['perfil'],activo=True,usuario__rol='OPERADOR_EMBARQUE',usuario__is_active=True,usuario__esta_activo=True)
                    op.embarcadores.set([perfil]);aviso_operacion(op,'Responsable de embarque actualizado.')
                    from .models import Aviso
                    Aviso.objects.create(perfil=perfil,texto=f'Embarque asignado: {s.fecha} {s.hora} · {s.origen} → {s.destino}')
                    messages.success(request,'Responsable de embarque asignado.')
                else:exigir(accion=='abrir','Acción inválida.')
        except (Problema,ValidationError,ValueError,KeyError,ObjectDoesNotExist) as e:messages.error(request,getattr(e,'mensaje',str(e)))
        from urllib.parse import urlencode
        return redirect('/movil/buses/?'+urlencode({'desde':request.POST.get('desde',str(desde)),'hasta':request.POST.get('hasta',str(hasta)),'salida':seleccion}))
    lista=list(Salida.objects.filter(importacion__estado='VALIDADO',fecha__range=(desde,hasta)).select_related('conductor_uno','conductor_dos').order_by('fecha','hora','pk'))
    from .programacion_manual import comprobar_descanso, firma_asignacion
    for salida in lista:
        salida.programacion_pendiente = (
            salida.original.get('origen_programacion') == 'MANUAL'
            and (not salida.original.get('publicacion_descanso_autorizada')
                 or salida.original.get('firma_asignacion_publicada') != firma_asignacion(salida)))
        salida.descanso_motivo = ''
        salida.descanso_revisado = request.GET.get('descanso_revisado') == '1'
        salida.requiere_cambio_conductor = False
        if salida.programacion_pendiente:
            operacion_salida = Operacion.objects.filter(salida=salida).first()
            if operacion_salida:
                permitido, motivo = comprobar_descanso(operacion_salida)
                salida.descanso_motivo = '' if permitido else motivo
                salida.requiere_cambio_conductor = (
                    'Descanso insuficiente' in salida.descanso_motivo
                    or 'Sin llegada real' in salida.descanso_motivo)
    seleccionada=Salida.objects.filter(pk=request.GET.get('salida'),importacion__estado='VALIDADO').first() if request.GET.get('salida','').isdigit() else None
    op=Operacion.objects.filter(salida=seleccionada).first() if seleccionada else None
    from .programacion_manual import firma_asignacion
    if op and op.salida.original.get('origen_programacion') == 'MANUAL':
        from .programacion_manual import comprobar_descanso
        _ok, _motivo = comprobar_descanso(op)
        seleccionada.descanso_motivo = '' if _ok else _motivo
        seleccionada.programacion_pendiente = not seleccionada.original.get(
            'publicacion_descanso_autorizada') or (
                seleccionada.original.get('firma_asignacion_publicada')
                != firma_asignacion(seleccionada))
        seleccionada.requiere_cambio_conductor = (
            'Descanso insuficiente' in seleccionada.descanso_motivo
            or 'Sin llegada real' in seleccionada.descanso_motivo)
    elif seleccionada:
        seleccionada.descanso_motivo = ''
        seleccionada.programacion_pendiente = False
    pisos=[];pasajeros=[];config={}
    if op:
        capacidad=seleccionada.comercial['capacidad'] or 0
        config=op.distribucion_asientos or {'piso1':12 if capacidad==60 else capacidad,'piso2':48 if capacidad==60 else 0,'numeracion':'continua','confirmada':False}
        pasajeros=list(op.pasajeros.order_by('piso','asiento'))
        ocupados={(p.piso,p.asiento):p for p in pasajeros}
        for piso in (1,2):
            plazas=[n for p,n in asientos_distribucion(config) if p==piso]
            if plazas:pisos.append({'numero':piso,'filas':[ [{'numero':n,'pasajero':ocupados.get((piso,n))} for n in plazas[i:i+(3 if piso==1 and config['piso2'] else 4)]] for i in range(0,len(plazas),3 if piso==1 and config['piso2'] else 4)],'columnas':3 if piso==1 and config['piso2'] else 4})
    from .descanso_publicacion import disponibilidad_conductor
    momento = (timezone.make_aware(
        datetime.combine(seleccionada.fecha, seleccionada.hora), PERU)
        if seleccionada else timezone.now())
    conductores_disponibilidad = []
    for perfil in Perfil.objects.filter(
            conductor__isnull=False, activo=True, usuario__is_active=True,
            usuario__esta_activo=True).select_related('conductor', 'usuario'):
        permitido, motivo, disponible_desde = disponibilidad_conductor(perfil, momento)
        conductores_disponibilidad.append({
            'pk': perfil.pk, 'nombre': perfil.conductor.nombre_apellidos,
            'codigo': perfil.codigo, 'disponible': permitido,
            'motivo': motivo,
            'desde': (disponible_desde.astimezone(PERU).strftime('%d/%m %H:%M')
                      if disponible_desde else ''),
        })
    return render(request,'movil/buses.html',{'desde':desde,'hasta':hasta,'viajes_buses':lista,'salida_bus':seleccionada,'operacion_bus':op,'pisos_bus':pisos,'pasajeros_bus':pasajeros,'config_bus':config,'salida_edit':seleccionada,'embarcadores_bus':Perfil.objects.filter(activo=True,usuario__rol='OPERADOR_EMBARQUE',usuario__is_active=True,usuario__esta_activo=True).select_related('usuario','trabajador'),'conductores_disponibilidad':conductores_disponibilidad})
