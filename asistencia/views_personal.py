from datetime import date
from calendar import monthrange
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from asistencia.models import Trabajador, DescansoProgramado, ProgramacionHorario, RevisionAsistencia, CierreAsistencia
from asistencia.forms_horarios import DIAS, ProgramarHorarioForm
from asistencia.services.revision import puede_gestionar, puede_aprobar, registrar_historial
from asistencia.services.reglas_jornada import normalizar


class FichaPersonalForm(forms.ModelForm):
    class Meta:
        model = Trabajador
        fields = ['nombres', 'apellido_paterno', 'apellido_materno', 'dni', 'area', 'sede']
        labels = {'area': 'Área', 'sede': 'Sede', 'dni': 'DNI'}


class VacacionesForm(forms.Form):
    desde = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    hasta = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))


class DescansoForm(forms.Form):
    desde = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    hasta = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    dias = forms.TypedMultipleChoiceField(choices=DIAS, coerce=int, required=False, widget=forms.CheckboxSelectMultiple, label='Días de descanso')

    def clean(self):
        datos = super().clean()
        if datos.get('desde') and datos.get('hasta') and not 0 <= (datos['hasta'] - datos['desde']).days <= 365:
            raise ValidationError('Seleccione una vigencia de hasta 366 días, con inicio anterior o igual al fin.')
        return datos


def retorno_asistencia(request):
    destino = request.POST.get('volver_a') or request.GET.get('volver_a', '')
    if destino.startswith('/') and not destino.startswith('//') and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return destino
    return ''


def contexto_personal(request):
    if not puede_gestionar(request.user):
        return {}
    hoy = timezone.localdate()
    q = request.GET.get('buscar_personal', '').strip()[:100]
    trabajadores = Trabajador.objects.prefetch_related('identidades', 'descansos_programados').order_by('nombre_completo', 'pk')
    if q:
        trabajadores = trabajadores.filter(Q(nombre_completo__icontains=q) | Q(dni__icontains=q) | Q(area__icontains=q) | Q(identidades__codigo__icontains=q)).distinct()
    pagina = Paginator(trabajadores, 25).get_page(request.GET.get('pagina_personal'))
    ids = [t.pk for t in pagina]
    horarios = {}
    for p in ProgramacionHorario.objects.filter(trabajador_id__in=ids, fecha__gte=hoy).select_related('turno').order_by('fecha'):
        horarios.setdefault(p.trabajador_id, p)
    for t in pagina:
        t.horario_personal = horarios.get(t.pk)
        t.descanso_personal = next((r for r in t.descansos_programados.all() if r.desde <= hoy <= r.hasta), None)
        t.descanso_etiqueta = ', '.join(dict(DIAS)[d] for d in t.descanso_personal.dias) if t.descanso_personal else 'Sin programar'
        t.nocturnas_personal = t.calcular_nocturnas if t.calcular_nocturnas is not None else not any(x in normalizar(t.area) for x in ['vigilante', 'vigilancia'])
    ficha = None
    if request.GET.get('ficha', '').isdigit():
        ficha = get_object_or_404(Trabajador.objects.prefetch_related('identidades', 'descansos_programados'), pk=request.GET['ficha'])
        descanso_actual = next((r for r in ficha.descansos_programados.all() if r.desde <= hoy <= r.hasta), None)
        ficha.dias_trabajo_actuales = [d for d in range(7) if descanso_actual is None or d not in descanso_actual.dias]
        ficha.nocturnas_personal = ficha.calcular_nocturnas if ficha.calcular_nocturnas is not None else not any(x in normalizar(ficha.area) for x in ['vigilante', 'vigilancia'])
    from asistencia.services.texto_historial import descripcion_historial
    historial = list(RevisionAsistencia.objects.filter(accion__in=['Ficha de personal', 'Descanso programado', 'Días de trabajo programados', 'Horario programado', 'Configuración de nocturnas', 'Configuración de extras', 'Modalidad de horas trabajadas', 'Vacaciones asignadas', 'Vacaciones validadas']).filter(Q(detalle__startswith=f'Trabajador #{ficha.pk}:') | Q(detalle__startswith=f'Trabajador #{ficha.pk} ')).select_related('responsable')[:30]) if ficha else []
    for registro in historial:
        registro.descripcion_legible = descripcion_historial(registro)
    return {'personal_volver_a': retorno_asistencia(request), 'dias_laborales_opciones': DIAS, 'personal_pagina': pagina, 'personal_buscar': q, 'personal_ficha': ficha,
            'personal_form': FichaPersonalForm(instance=ficha) if ficha else None,
            'descanso_form': DescansoForm(initial={'desde': hoy, 'hasta': date(hoy.year, 12, 31)}) if ficha else None,
            'horario_personal_form': ProgramarHorarioForm(prefix='horario', initial={'trabajador': ficha.pk, 'desde': hoy, 'hasta': hoy.replace(day=monthrange(hoy.year,hoy.month)[1]), 'dias': list(range(7))}) if ficha else None,
            'personal_historial': historial,
            'vacaciones_form': VacacionesForm(prefix='vacaciones', initial={'desde': hoy, 'hasta': hoy}) if ficha else None,
            'personal_vacaciones': ficha.periodos_vacaciones.all() if ficha else [],
            'personal_descansos': ficha.descansos_programados.all()[:10] if ficha else [],
            'personal_query': urlencode({'vista': 'personal', 'buscar_personal': q})}


@login_required
@require_POST
def guardar_personal(request, trabajador_id):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden('No tiene permiso para configurar personal.')
    try:
        with transaction.atomic():
            t = get_object_or_404(Trabajador.objects.select_for_update(), pk=trabajador_id)
            accion = request.POST.get('accion')
            if accion == 'datos':
                form = FichaPersonalForm(request.POST, instance=t)
                if not form.is_valid():
                    raise ValidationError(' '.join(f'{campo}: {error}' for campo, errores in form.errors.items() for error in errores))
                original = Trabajador.objects.get(pk=t.pk)
                antes = {c: getattr(original, c) for c in form.Meta.fields}
                form.save()
                registrar_historial(None, request.user, 'Ficha de personal', f'Trabajador #{t.pk}: antes={antes}; ahora={form.cleaned_data}.')
            elif accion == 'horario':
                datos_post = request.POST.copy()
                datos_post['horario-trabajador'] = str(t.pk)
                form = ProgramarHorarioForm(datos_post, prefix='horario')
                if not form.is_valid():
                    raise ValidationError(' '.join(f'{campo}: {error}' for campo, errores in form.errors.items() for error in errores))
                datos = form.cleaned_data
                from asistencia.services.horarios import programar_horarios
                programar_horarios(t, datos['desde'], datos['hasta'], datos['dias'], datos['turno'], datos['motivo'], request.user)
            elif accion == 'extras':
                from asistencia.services.configuracion_horas import configurar_extras
                configurar_extras(t, request.POST.get('calcular_extras_25') == 'si', request.POST.get('calcular_extras_35') == 'si', request.user)
            elif accion == 'dias_laborales':
                if not puede_aprobar(request.user):
                    raise ValidationError('La programación corresponde a Contabilidad o Gerencia.')
                form = DescansoForm(request.POST)
                if not form.is_valid():
                    raise ValidationError('Revise las fechas y los días seleccionados.')
                datos = form.cleaned_data
                if CierreAsistencia.objects.filter(fecha_inicio__lte=datos['hasta'], fecha_fin__gte=datos['desde']).exists():
                    raise ValidationError('Seleccione fechas fuera de los periodos cerrados.')
                dias_trabajo = datos['dias']
                if not dias_trabajo:
                    raise ValidationError('Seleccione al menos un día de trabajo.')
                DescansoProgramado.objects.create(trabajador=t, responsable=request.user, desde=datos['desde'], hasta=datos['hasta'], dias=[d for d in range(7) if d not in dias_trabajo], sin_trabajo_programado=True)
                registrar_historial(None, request.user, 'Días de trabajo programados', f'Trabajador #{t.pk}: {datos}. Los días restantes quedan sin trabajo programado, pendiente de confirmación en Asistencia.')
            elif accion == 'solo_horas':
                from asistencia.services.configuracion_horas import configurar_solo_horas
                configurar_solo_horas(t, request.POST.get('solo_horas_trabajadas') == 'si', request.user)
            elif accion == 'nocturnas':
                from asistencia.services.configuracion_nocturnas import configurar_nocturnas
                configurar_nocturnas(t, request.POST.get('calcular_nocturnas') == 'si', request.user)
            elif accion == 'vacaciones':
                form = VacacionesForm(request.POST, prefix='vacaciones')
                if not form.is_valid():
                    raise ValidationError('Indique las fechas de inicio y fin de vacaciones.')
                from asistencia.services.vacaciones import asignar_vacaciones
                asignar_vacaciones(t, form.cleaned_data['desde'], form.cleaned_data['hasta'], request.user)
            elif accion == 'descanso':
                if not puede_aprobar(request.user):
                    raise ValidationError('La programación de descansos corresponde a Contabilidad o Gerencia.')
                form = DescansoForm(request.POST)
                if not form.is_valid():
                    raise ValidationError(' '.join(str(e) for errores in form.errors.values() for e in errores))
                datos = form.cleaned_data
                if CierreAsistencia.objects.filter(fecha_inicio__lte=datos['hasta'], fecha_fin__gte=datos['desde']).exists():
                    raise ValidationError('La vigencia incluye un periodo cerrado. Seleccione fechas abiertas.')
                DescansoProgramado.objects.create(trabajador=t, responsable=request.user, **datos)
                registrar_historial(None, request.user, 'Descanso programado', f'Trabajador #{t.pk}: {datos}. Solo programación; no aprueba días ni genera asistencias.')
            else:
                raise ValidationError('Seleccione una opción de configuración válida.')
        messages.success(request, 'Configuración del trabajador guardada.', extra_tags='personal-config')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages), extra_tags='personal-config')
    destino = {'vista': 'personal', 'ficha': trabajador_id}
    if retorno_asistencia(request):
        destino['volver_a'] = retorno_asistencia(request)
    return redirect(reverse('dashboard') + '?' + urlencode(destino))
