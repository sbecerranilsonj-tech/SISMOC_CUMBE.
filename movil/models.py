import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class Perfil(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    codigo = models.CharField(max_length=20, unique=True, blank=True)
    trabajador = models.OneToOneField('asistencia.Trabajador', null=True, blank=True, on_delete=models.PROTECT)
    conductor = models.OneToOneField('conductores.Conductor', null=True, blank=True, on_delete=models.PROTECT)
    permisos = models.JSONField(default=list, blank=True)
    activo = models.BooleanField(default=True)
    activado = models.BooleanField(default=False)
    activacion_hash = models.CharField(max_length=128, blank=True)
    activacion_hasta = models.DateTimeField(null=True, blank=True)
    dispositivo = models.CharField(max_length=100, blank=True)
    requiere_rostro = models.BooleanField(default=False)
    rostro = models.TextField(blank=True, help_text='Plantilla facial cifrada. No contiene fotografías.')
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = 'CUM-' + uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)
    def __str__(self):
        return f'{self.codigo} · {self.usuario.nombre_completo}'
    @property
    def estado_acceso(self):
        if not self.activo or not self.usuario.is_active or not self.usuario.esta_activo:
            return 'Deshabilitado'
        if self.activado:
            return 'Activado'
        if self.activacion_hasta and self.activacion_hasta <= timezone.now():
            return 'Código vencido'
        return 'Pendiente'
    def clean(self):
        if self.trabajador_id and self.trabajador.usuario_id not in (None,self.usuario_id):
            raise ValidationError('La ficha está vinculada a otra cuenta.')
        if self.conductor_id and self.conductor.trabajador_id and self.conductor.trabajador_id != self.trabajador_id:
            raise ValidationError('El conductor pertenece a otra ficha de trabajador.')


class Sesion(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    vence = models.DateTimeField()
    activa = models.BooleanField(default=True)


class Zona(models.Model):
    area = models.CharField(max_length=150, blank=True)
    nombre = models.CharField(max_length=150)
    sede = models.CharField(max_length=100)
    latitud = models.FloatField()
    longitud = models.FloatField()
    radio = models.PositiveIntegerField(default=100)
    precision_maxima = models.PositiveIntegerField(default=50)
    perfiles = models.ManyToManyField(Perfil, blank=True)
    activa = models.BooleanField(default=True)
    def __str__(self):
        return f'{self.sede} · {self.nombre}'


class Comision(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.PROTECT)
    motivo = models.CharField(max_length=500)
    desde = models.DateTimeField()
    hasta = models.DateTimeField()
    sin_rostro = models.BooleanField(default=False)
    autorizada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class Registro(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    perfil = models.ForeignKey(Perfil, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=25)
    recibido = models.DateTimeField(auto_now_add=True)
    fecha_dispositivo = models.DateTimeField(null=True, blank=True)
    jornada = models.DateField()
    latitud = models.FloatField(null=True)
    longitud = models.FloatField(null=True)
    precision = models.FloatField(null=True)
    zona = models.ForeignKey(Zona, null=True, on_delete=models.PROTECT)
    comision = models.ForeignKey(Comision, null=True, on_delete=models.PROTECT)
    facial = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, default='REGISTRADO')
    motivo = models.CharField(max_length=500, blank=True)
    marca = models.OneToOneField('asistencia.MarcacionBiometrica', null=True, on_delete=models.PROTECT)


class Solicitud(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20)
    desde = models.DateField()
    hasta = models.DateField()
    detalle = models.TextField(max_length=2000)
    emergencia = models.BooleanField(default=False)
    datos = models.JSONField(default=dict)
    estado = models.CharField(max_length=15, default='PENDIENTE')
    respuesta = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)


class Operacion(models.Model):
    salida = models.OneToOneField('conductores.Salida', on_delete=models.PROTECT)
    estado = models.CharField(max_length=15, default='PROGRAMADO')
    embarcadores = models.ManyToManyField(Perfil, blank=True)
    permite_embarque_conductor = models.BooleanField(default=False)
    salida_real = models.DateTimeField(null=True, blank=True)
    llegada_real = models.DateTimeField(null=True, blank=True)
    conduciendo = models.ForeignKey(Perfil, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    relevo_pendiente = models.ForeignKey(Perfil, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    cambio_manual = models.BooleanField(default=False)
    fin_previsto = models.DateTimeField(null=True, blank=True)


class EventoViaje(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operacion = models.ForeignKey(Operacion, on_delete=models.PROTECT, related_name='eventos')
    perfil = models.ForeignKey(Perfil, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=30)
    creado = models.DateTimeField(auto_now_add=True)
    datos = models.JSONField(default=dict)


class Descanso(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.PROTECT)
    operacion = models.ForeignKey(Operacion, on_delete=models.PROTECT)
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)


class ReglaDescanso(models.Model):
    activa = models.BooleanField(default=False, help_text='Activar solo después de confirmar la regla de la empresa.')
    horas = models.PositiveIntegerField(default=8)


class Pasajero(models.Model):
    operacion = models.ForeignKey(Operacion, on_delete=models.PROTECT, related_name='pasajeros')
    referencia = models.CharField(max_length=100)
    nombre = models.CharField(max_length=180)
    documento = models.CharField(max_length=25)
    edad = models.PositiveIntegerField(null=True, blank=True)
    piso = models.PositiveIntegerField(default=1)
    asiento = models.PositiveIntegerField()
    origen = models.CharField(max_length=120)
    destino = models.CharField(max_length=120)
    punto = models.CharField(max_length=150)
    estado = models.CharField(max_length=20, default='PENDIENTE')
    verificado_por = models.ForeignKey(Perfil, null=True, blank=True, on_delete=models.PROTECT)
    verificado_el = models.DateTimeField(null=True, blank=True)
    sincronizacion_id = models.UUIDField(null=True, blank=True, unique=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['operacion', 'referencia'], name='movil_reserva_unica')]


class Incidencia(models.Model):
    operacion = models.ForeignKey(Operacion, on_delete=models.PROTECT)
    perfil = models.ForeignKey(Perfil, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=40)
    descripcion = models.TextField(max_length=2000)
    estado = models.CharField(max_length=20, default='REPORTADO')
    creado = models.DateTimeField(auto_now_add=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)


class Pago(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.PROTECT)
    desde = models.DateField()
    hasta = models.DateField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    referencia = models.CharField(max_length=150)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['perfil','referencia'], name='movil_pago_referencia_unica')]


class Aviso(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE)
    texto = models.CharField(max_length=500)
    creado = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)


class Auditoria(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='auditoria_movil')
    accion = models.CharField(max_length=100)
    detalle = models.JSONField(default=dict)
    creado = models.DateTimeField(auto_now_add=True)


class IntentoAcceso(models.Model):
    clave = models.CharField(max_length=64, unique=True)
    intentos = models.PositiveIntegerField(default=0)
    desde = models.DateTimeField()
