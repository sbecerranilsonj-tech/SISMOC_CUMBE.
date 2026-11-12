from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin
from asistencia.forms_reglas import ReglaJornadaForm, DiaEspecialForm
from asistencia.models import ReglaJornada, DiaEspecial, Trabajador, ResumenAsistenciaDiaria, CierreAsistencia
from asistencia.services.reglas_jornada import normalizar, feriados_nacionales
from asistencia.services.revision import puede_gestionar, dejar_pendiente, registrar_historial


@login_required
@xframe_options_sameorigin
@require_http_methods(['GET', 'POST'])
def reglas_jornada(request):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden('No tiene permiso para configurar jornadas.')
    popup = request.GET.get('popup') == '1'
    apartado_dias = request.GET.get('apartado') == 'dias' or request.POST.get('accion') == 'dia_especial'
    hoy = timezone.localdate()
    initial = {'desde': hoy}
    if request.GET.get('trabajador', '').isdigit():
        initial['trabajador'] = request.GET['trabajador']
    form = ReglaJornadaForm(prefix='regla', initial=initial)
    especial = DiaEspecialForm(prefix='especial')
    if request.method == 'POST':
        es_dia = request.POST.get('accion') == 'dia_especial'
        elegido = DiaEspecialForm(request.POST, prefix='especial') if es_dia else ReglaJornadaForm(request.POST, prefix='regla')
        if es_dia:
            especial = elegido
        else:
            form = elegido
        if elegido.is_valid():
            try:
                with transaction.atomic():
                    # Serializar cambios de configuración para evitar reglas simultáneas contradictorias.
                    get_user_model().objects.select_for_update().get(pk=request.user.pk)
                    obj = elegido.save(commit=False)
                    inicio = obj.fecha if es_dia else obj.desde
                    fin = obj.fecha if es_dia else (obj.hasta or date.max)
                    if CierreAsistencia.objects.filter(fecha_inicio__lte=fin, fecha_fin__gte=inicio).exists():
                        raise ValidationError('La vigencia incluye un periodo cerrado. Elija fechas abiertas.')
                    obj.responsable = request.user
                    obj.save()
                    if not es_dia:
                        jornadas = ResumenAsistenciaDiaria.objects.filter(fecha__range=(inicio, fin))
                        if obj.trabajador_id:
                            from django.db.models import Q
                            consulta = Q(trabajador_id=obj.trabajador_id)
                            if obj.trabajador.usuario_id:
                                consulta |= Q(trabajador__isnull=True, usuario_id=obj.trabajador.usuario_id)
                            jornadas = jornadas.filter(consulta)
                        elif obj.area:
                            ids = [t.pk for t in Trabajador.objects.all() if normalizar(t.area) == normalizar(obj.area)]
                            jornadas = jornadas.filter(trabajador_id__in=ids)
                        for jornada in jornadas.select_for_update(of=('self',)):
                            dejar_pendiente(jornada, request.user, f'Regla #{obj.pk}: {obj.motivo}. Validar nuevamente los cálculos.')
                    registrar_historial(None, request.user, 'Día especial registrado' if es_dia else 'Regla de jornada registrada',
                                        f'#{obj.pk}: {inicio} a {fin}; {obj.nombre if es_dia else obj.motivo}')
                messages.success(request, 'Día especial guardado. Revise la situación de cada trabajador.' if es_dia else 'Regla guardada. Las jornadas afectadas quedan pendientes de validar.')
                return redirect(reverse('reglas_jornada') + ('?apartado=dias' if es_dia else '?apartado=jornadas') + ('&popup=1' if popup else ''))
            except ValidationError as exc:
                elegido.add_error(None, exc)
    return render(request, 'asistencia/reglas_jornada.html', {
        'popup': popup, 'apartado_dias': apartado_dias, 'form': form, 'especial': especial, 'reglas': ReglaJornada.objects.select_related('trabajador', 'responsable')[:100],
        'especiales': DiaEspecial.objects.all(), 'feriados': sorted(feriados_nacionales(hoy.year).items()),
        'anio': hoy.year, 'areas': sorted(set(Trabajador.objects.values_list('area', flat=True))),
    })
