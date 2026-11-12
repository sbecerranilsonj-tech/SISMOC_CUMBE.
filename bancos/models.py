from decimal import Decimal
from django.conf import settings
from django.db import models
from .storage import almacen_privado


class EstadoCuenta(models.Model):
    cuenta = models.CharField(max_length=40)
    moneda = models.CharField(max_length=12, default='SOLES')
    inicio = models.DateField()
    fin = models.DateField()
    saldo_inicial = models.DecimalField(max_digits=16, decimal_places=2)
    saldo_final = models.DecimalField(max_digits=16, decimal_places=2)
    huella = models.CharField(max_length=64, unique=True)
    pdf = models.FileField(storage=almacen_privado, upload_to='estados/%Y/%m/')
    incidencias = models.JSONField(default=list)
    estado = models.CharField(max_length=12, default='PENDIENTE', choices=[('PENDIENTE', 'Pendiente'), ('VALIDADO', 'Validado')])
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='estados_importados')
    creado = models.DateTimeField(auto_now_add=True)
    validado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='estados_validados')
    validado = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-inicio', '-pk']

    @property
    def diferencia(self):
        neto = sum((m.abono - m.cargo for m in self.movimientos.all()), Decimal('0.00'))
        return self.saldo_inicial + neto - self.saldo_final


class Movimiento(models.Model):
    estado_cuenta = models.ForeignKey(EstadoCuenta, on_delete=models.CASCADE, related_name='movimientos')
    orden = models.PositiveIntegerField()
    pagina = models.PositiveIntegerField()
    fecha = models.DateField()
    fecha_valor = models.DateField()
    descripcion = models.CharField(max_length=500)
    cargo = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    abono = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    original = models.JSONField(default=dict)
    observacion = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['fecha', 'orden']
        constraints = [models.UniqueConstraint(fields=['estado_cuenta', 'orden'], name='bancos_orden_unico')]


class Revision(models.Model):
    @property
    def cambios_legibles(self):
        etiquetas = {'fecha': 'Fecha', 'fecha_valor': 'Fecha valor', 'descripcion': 'Descripción', 'cargo': 'Cargo', 'abono': 'Abono', 'observacion': 'Motivo / observación'}
        antes = self.detalle.get('antes', {})
        despues = self.detalle.get('despues', {})
        return [{'campo': etiqueta, 'antes': antes.get(campo) or 'Sin registrar', 'despues': despues.get(campo) or 'Sin registrar'} for campo, etiqueta in etiquetas.items() if antes.get(campo) != despues.get(campo)]

    estado_cuenta = models.ForeignKey(EstadoCuenta, on_delete=models.CASCADE, related_name='revisiones')
    movimiento = models.ForeignKey(Movimiento, on_delete=models.PROTECT, null=True, blank=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    detalle = models.JSONField(default=dict)
