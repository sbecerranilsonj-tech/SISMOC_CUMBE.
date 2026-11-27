from django import forms
from asistencia.models import ReglaJornada, DiaEspecial


class ReglaJornadaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from asistencia.models import Trabajador
        from asistencia.services.reglas_jornada import normalizar
        areas = {}
        for area in Trabajador.objects.order_by('area').values_list('area', flat=True).distinct():
            area = ' '.join((area or '').split())
            if area:
                areas.setdefault(normalizar(area), area)
        self.fields['area'] = forms.ChoiceField(required=False, label='Área',
            choices=[('', 'General / excepción individual')] + [(a, a) for a in sorted(areas.values())])

    class Meta:
        model = ReglaJornada
        fields = ['area', 'trabajador', 'desde', 'hasta', 'minutos_diarios', 'minutos_sabado', 'minutos_refrigerio', 'exento_marcacion', 'motivo']
        labels = {'area': 'Área (vacía: general)', 'trabajador': 'Excepción individual (opcional)',
                  'desde': 'Vigente desde', 'hasta': 'Hasta (opcional)', 'minutos_diarios': 'Jornada de lunes a viernes (min)',
                  'minutos_sabado': 'Jornada del sábado (min)', 'minutos_refrigerio': 'Refrigerio (min)',
                  'exento_marcacion': 'Exonerar obligación de marcar', 'motivo': 'Motivo del cambio'}
        widgets = {'desde': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'hasta': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def clean(self):
        datos = super().clean()
        datos['area'] = ' '.join(datos.get('area', '').split())
        if datos.get('area') and datos.get('trabajador'):
            raise forms.ValidationError('Seleccione un área o un trabajador, no ambos.')
        if datos.get('exento_marcacion') and not datos.get('trabajador'):
            raise forms.ValidationError('La exoneración debe asignarse a una persona concreta.')
        if datos.get('hasta') and datos.get('desde') and datos['hasta'] < datos['desde']:
            raise forms.ValidationError('La fecha final debe ser igual o posterior al inicio.')
        return datos


class DiaEspecialForm(forms.ModelForm):
    class Meta:
        model = DiaEspecial
        fields = ['fecha', 'nombre', 'tipo']
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}
