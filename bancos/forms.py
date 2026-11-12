from django import forms
from .models import Movimiento


class ImportarForm(forms.Form):
    pdf = forms.FileField(label='Estado de cuenta BCP en PDF', widget=forms.FileInput(attrs={'accept': '.pdf'}))

    def clean_pdf(self):
        archivo = self.cleaned_data['pdf']
        if archivo.size > 20 * 1024 * 1024:
            raise forms.ValidationError('El límite es de 20 MB.')
        if not archivo.name.strip().lower().endswith('.pdf'):
            raise forms.ValidationError('El archivo debe tener extensión .pdf.')
        # Algunos emisores anteponen espacios, un BOM o un preámbulo al PDF.
        # La comprobación definitiva de su estructura la realiza el lector PDF.
        archivo.seek(0)
        cabecera = archivo.read(1024)
        archivo.seek(0)
        if b'%PDF-' not in cabecera:
            raise forms.ValidationError('El contenido del archivo no contiene una cabecera PDF reconocible. Vuelva a descargar el estado de cuenta original del BCP; cambiar la extensión de un archivo no lo convierte en PDF.')
        return archivo


class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ['fecha', 'fecha_valor', 'descripcion', 'cargo', 'abono', 'observacion']
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'), 'fecha_valor': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def clean(self):
        datos = super().clean()
        cargo, abono = datos.get('cargo'), datos.get('abono')
        if cargo is not None and abono is not None and (cargo < 0 or abono < 0 or (cargo > 0) == (abono > 0)):
            raise forms.ValidationError('Registre un importe positivo en cargo o abono, solo en una columna.')
        fecha = datos.get('fecha')
        estado = self.instance.estado_cuenta
        if fecha and not estado.inicio <= fecha <= estado.fin:
            raise forms.ValidationError('La fecha debe pertenecer al período del estado de cuenta.')
        return datos
