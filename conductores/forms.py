from django import forms
from .models import Conductor, SituacionConductor


class ImportarForm(forms.Form):
    archivo = forms.FileField(label='Reporte de itinerarios', widget=forms.ClearableFileInput(attrs={'accept': '.xls,.xlsx,.xlsm'}))

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        if not archivo.name.lower().endswith(('.xls', '.xlsx', '.xlsm')):
            raise forms.ValidationError('Seleccione un archivo XLS, XLSX o XLSM.')
        if archivo.size > 20 * 1024 * 1024:
            raise forms.ValidationError('El archivo no debe superar 20 MB.')
        return archivo


class SituacionForm(forms.Form):
    conductor = forms.ModelChoiceField(queryset=Conductor.objects.all())
    tipo = forms.ChoiceField(choices=[(valor, etiqueta) for valor, etiqueta in SituacionConductor.TIPOS if valor != 'LICENCIA'])
    inicio = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fin = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    motivo = forms.CharField(max_length=500, required=False, label='Motivo (opcional)', widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        conductores = sorted(Conductor.objects.select_related('trabajador'), key=lambda c: c.nombre_apellidos)
        self.fields['conductor'].choices = [('', 'Selecciona un conductor')] + [(c.pk, c.nombre_apellidos) for c in conductores]


class PeriodoForm(forms.Form):
    desde = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    hasta = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    q = forms.CharField(required=False, label='Buscar conductor', max_length=180)

    def clean(self):
        datos = super().clean()
        if datos.get('desde') and datos.get('hasta'):
            delta = (datos['hasta']-datos['desde']).days
            if not 0 <= delta <= 61:
                raise forms.ValidationError('Seleccione un período de entre 1 y 62 días.')
        return datos


class ConductorForm(forms.ModelForm):
    nombres = forms.CharField(max_length=100, label='Nombres')
    apellido_paterno = forms.CharField(max_length=60, label='Primer apellido')
    apellido_materno = forms.CharField(max_length=60, required=False, label='Segundo apellido')

    class Meta:
        model = Conductor
        fields = ['apellido_paterno', 'apellido_materno', 'nombres']

    def clean(self):
        datos = super().clean()
        for campo in self.Meta.fields:
            if campo in datos:
                datos[campo] = ' '.join(datos[campo].upper().split())
        if len(' '.join(datos.get(campo, '') for campo in self.Meta.fields)) > 180:
            raise forms.ValidationError('El nombre completo no debe superar 180 caracteres.')
        return datos
