from django import forms
from asistencia.models import Trabajador, TurnoHorario

DIAS = list(enumerate(['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']))


class ProgramarHorarioForm(forms.Form):
    trabajador = forms.ModelChoiceField(queryset=Trabajador.objects.all(), label='Trabajador')
    desde = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}, format='%Y-%m-%d'))
    hasta = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}, format='%Y-%m-%d'))
    dias = forms.TypedMultipleChoiceField(choices=DIAS, coerce=int, widget=forms.CheckboxSelectMultiple, initial=list(range(7)), label='Días a programar')
    turno = forms.ModelChoiceField(queryset=TurnoHorario.objects.filter(activo=True), label='Horario confirmado')
    motivo = forms.CharField(max_length=500, required=False, label='Referencia de la programación (opcional)', widget=forms.TextInput(attrs={'placeholder':'Ej.: cambio temporal o reemplazo de compañero'}))
    confirmado = forms.BooleanField(label='Confirmo que este horario corresponde a las fechas seleccionadas.')

    def clean(self):
        data=super().clean()
        if data.get('desde') and data.get('hasta') and not 0 <= (data['hasta']-data['desde']).days <= 365:
            raise forms.ValidationError('El rango debe ser de 1 a 366 días, con la fecha final posterior o igual a la inicial.')
        return data


class TurnoConfirmadoForm(forms.ModelForm):
    class Meta:
        model=TurnoHorario
        fields=['nombre','hora_entrada','hora_salida','evaluar_tardanzas','tolerancia_minutos','hora_inicio_refrigerio','hora_fin_refrigerio']
        widgets={key:forms.TimeInput(attrs={'type':'time'}) for key in ['hora_entrada','hora_salida','hora_inicio_refrigerio','hora_fin_refrigerio']}

    def clean_tolerancia_minutos(self):
        n=self.cleaned_data['tolerancia_minutos']
        if n>120: raise forms.ValidationError('La tolerancia debe estar entre 0 y 120 minutos.')
        return n

    def clean(self):
        data=super().clean()
        entrada,salida=data.get('hora_entrada'),data.get('hora_salida')
        inicio,fin=data.get('hora_inicio_refrigerio'),data.get('hora_fin_refrigerio')
        if entrada and salida and entrada==salida:
            raise forms.ValidationError('La entrada y la salida deben ser diferentes.')
        if bool(inicio)!=bool(fin):
            raise forms.ValidationError('Complete ambas horas de refrigerio o deje ambas vacías.')
        if entrada and salida and inicio and fin:
            minutes=lambda t:t.hour*60+t.minute
            duracion=(minutes(salida)-minutes(entrada))%1440
            a,b=(minutes(inicio)-minutes(entrada))%1440,(minutes(fin)-minutes(entrada))%1440
            if not 0<a<b<duracion: raise forms.ValidationError('El refrigerio debe comenzar y terminar dentro del turno, en ese orden.')
        return data
