from calendar import monthrange
from datetime import date
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin
from asistencia.models import ProgramacionHorario, TurnoHorario, Trabajador
from asistencia.forms_horarios import ProgramarHorarioForm, TurnoConfirmadoForm
from asistencia.services.horarios import programar_horarios
from asistencia.services.revision import puede_gestionar, registrar_historial


@login_required
@require_http_methods(['GET','POST'])
@xframe_options_sameorigin
def horarios(request):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden('No tiene permiso para programar horarios.')
    hoy=timezone.localdate()
    try:
        desde=date.fromisoformat(request.GET.get('desde') or hoy.replace(day=1).isoformat())
        hasta=date.fromisoformat(request.GET.get('hasta') or hoy.replace(day=monthrange(hoy.year,hoy.month)[1]).isoformat())
        if hasta<desde or (hasta-desde).days>365: raise ValueError
    except ValueError:
        desde=hoy.replace(day=1); hasta=hoy.replace(day=monthrange(hoy.year,hoy.month)[1])
        messages.error(request,'Revise el rango de fechas. Se muestra el mes actual.')
    trabajador=request.GET.get('trabajador','')
    initial={'desde':desde,'hasta':hasta,'trabajador':trabajador}
    form=ProgramarHorarioForm(initial=initial)
    catalogo=TurnoConfirmadoForm(prefix='nuevo')
    if request.method=='POST':
        if request.POST.get('accion') == 'puntualidad_turno':
            turno = get_object_or_404(TurnoHorario, pk=request.POST.get('turno_id'), activo=True)
            turno.evaluar_tardanzas = request.POST.get('evaluar_tardanzas') == 'si'
            turno.save(update_fields=['evaluar_tardanzas'])
            registrar_historial(None, request.user, 'Puntualidad del horario', f'Horario #{turno.pk}: evaluar tardanzas={turno.evaluar_tardanzas}. Las jornadas cerradas no se recalculan.')
            messages.success(request, 'Configuración guardada. Se aplicará al validar las jornadas de este horario.')
            return redirect(request.get_full_path())
        if request.POST.get('accion')=='crear_turno':
            catalogo=TurnoConfirmadoForm(request.POST, prefix='nuevo')
            if catalogo.is_valid():
                turno=catalogo.save()
                registrar_historial(None,request.user,'Horario registrado',f'Horario #{turno.pk}: {turno}; tolerancia {turno.tolerancia_minutos} min; refrigerio {turno.hora_inicio_refrigerio} a {turno.hora_fin_refrigerio}.')
                messages.success(request,'Horario registrado. Ahora puede asignarlo a un trabajador.')
                return redirect(request.get_full_path())
        else:
            form=ProgramarHorarioForm(request.POST)
            if form.is_valid():
                data=form.cleaned_data
                try:
                    resultado=programar_horarios(data['trabajador'],data['desde'],data['hasta'],data['dias'],data['turno'],data['motivo'],request.user)
                    messages.success(request,f"{resultado['programadas']} fechas programadas; {resultado['actualizadas']} jornadas actualizadas; {resultado['reagrupadas']} jornadas nocturnas reagrupadas; {resultado['reabiertas']} aprobadas vuelven a revisión; {resultado['sin_cambios']} fechas sin cambios.")
                    return redirect(reverse('programar_horarios')+'?'+urlencode({'desde':data['desde'],'hasta':data['hasta'],'trabajador':data['trabajador'].pk}))
                except ValidationError as exc:
                    form.add_error(None,' '.join(exc.messages))
    personas = list(Trabajador.objects.prefetch_related('identidades').all())
    from asistencia.services.reglas_jornada import normalizar
    opciones = [{'id': str(p.pk), 'label': f'{p.nombre_corto} · {p.dni}',
                 'search': f'{p.nombre_completo} {p.nombre_corto} {p.dni} {p.codigo}'} for p in personas]
    busqueda = request.GET.get('buscar_horario', '').strip()[:150]
    seleccionado = next((p for p in opciones if p['id'] == trabajador), None)
    qs=ProgramacionHorario.objects.select_related('trabajador','turno','responsable').all()
    if trabajador.isdigit(): qs=qs.filter(trabajador_id=int(trabajador))
    elif busqueda:
        ids = [p['id'] for p in opciones if normalizar(busqueda) in normalizar(p['search'])]
        qs = qs.filter(trabajador_id__in=ids)
    query=urlencode({'trabajador':trabajador, 'buscar_horario':busqueda})
    from asistencia.services.grupos_horarios import agrupar_programacion
    grupos = agrupar_programacion(qs)
    return render(request,'asistencia/horarios.html',{'form':form,'catalogo':catalogo,'mostrar_catalogo':catalogo.is_bound,'programacion':Paginator(grupos,15).get_page(request.GET.get('pagina')),'desde':desde,'hasta':hasta,'trabajador_filtro':trabajador,'trabajadores':personas,'opciones_horarios':opciones,'buscar_horario':seleccionado['label'] if seleccionado else busqueda,'turnos':TurnoHorario.objects.filter(activo=True),'query':query})
