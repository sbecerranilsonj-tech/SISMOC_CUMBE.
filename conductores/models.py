from django.conf import settings
from django.db import models
from .storage import almacen_itinerarios


class Conductor(models.Model):
    nombre = models.CharField(max_length=180)
    nombres = models.CharField(max_length=100, blank=True, default='')
    apellido_paterno = models.CharField(max_length=60, blank=True, default='')
    apellido_materno = models.CharField(max_length=60, blank=True, default='')
    trabajador = models.OneToOneField('asistencia.Trabajador', null=True, blank=True, on_delete=models.PROTECT)

    @property
    def nombre_apellidos(self):
        if self.nombres and self.apellido_paterno:
            return ' '.join(filter(None, (self.apellido_paterno, self.apellido_materno, self.nombres))).upper()
        if self.trabajador_id and self.trabajador.apellido_paterno and self.trabajador.nombres:
            return ' '.join(filter(None, (self.trabajador.apellido_paterno, self.trabajador.apellido_materno, self.trabajador.nombres))).upper()
        partes = self.nombre.strip().upper().split()
        # Este nombre ya viene con apellidos primero en el reporte original.
        from .parser import normalizar
        if normalizar(self.nombre) == 'SALDANA SANGAY ANSELMO' or len(partes) < 3:
            return ' '.join(partes)
        # Formato del reporte de salidas: nombre(s), apellido paterno y materno.
        return ' '.join(partes[-2:] + partes[:-2])

    class Meta:
        ordering = ['nombre', 'pk']

    def __str__(self):
        return self.nombre_apellidos


class IdentidadConductor(models.Model):
    nombre_origen = models.CharField(max_length=220, unique=True)
    conductor = models.ForeignKey(Conductor, on_delete=models.PROTECT, related_name='identidades')


class Importacion(models.Model):
    nombre = models.CharField(max_length=255)
    huella = models.CharField(max_length=64, unique=True)
    archivo = models.FileField(storage=almacen_itinerarios, upload_to='itinerarios/%Y/%m/')
    inicio = models.DateField()
    fin = models.DateField()
    estado = models.CharField(max_length=12, default='PENDIENTE', choices=[('PENDIENTE', 'Pendiente'), ('VALIDADO', 'Validado')])
    incidencias = models.JSONField(default=list)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='itinerarios_importados')
    creado = models.DateTimeField(auto_now_add=True)
    validado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='itinerarios_validados')
    validado = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado']


class Salida(models.Model):
    estado_operativo = models.CharField(max_length=10, default='AUTO', choices=[('AUTO', 'Según reporte'), ('PROGRAMADO', 'Programado en aplicativo'), ('REALIZADO', 'Salida realizada'), ('CANCELADO', 'Salida cancelada')])

    @property
    def pendiente_salida(self):
        return not self.anulado and self.estado_operativo == 'AUTO' and self.pasajes_vendidos == 0

    @property
    def cuenta_para_control(self):
        return not self.anulado and self.estado_operativo not in ('CANCELADO','PROGRAMADO') and not self.pendiente_salida

    @property
    def estado_control(self):
        if self.estado_operativo == 'PROGRAMADO' and not self.anulado:
            return 'Programado · pendiente de finalizar en la app'
        if self.anulado or self.estado_operativo == 'CANCELADO':
            return 'Cancelado'
        if self.pendiente_salida:
            return 'Sin ventas · por confirmar'
        return 'Realizado' if self.estado_operativo == 'REALIZADO' else 'Activo'

    @property
    def comercial(self):
        vacios = {'capacidad': None, 'vendidos_primer_piso': None, 'vendidos_segundo_piso': None}
        datos = self.original.get('comercial')
        if datos is not None:
            return {**vacios, **datos}
        # Compatibilidad con reportes importados antes de nombrar las columnas.
        from decimal import Decimal, InvalidOperation
        datos = {}
        for nombre, posicion in [('capacidad', '9'), ('vendidos_segundo_piso', '10'), ('vendidos_primer_piso', '12')]:
            try:
                valor = Decimal(str(self.original.get(posicion, '')))
                if valor.is_finite() and valor >= 0 and valor == valor.to_integral_value():
                    datos[nombre] = int(valor)
            except InvalidOperation:
                pass
        return {**vacios, **datos}

    @property
    def pasajes_vendidos(self):
        datos = self.comercial
        if datos.get('vendidos_primer_piso') is not None and datos.get('vendidos_segundo_piso') is not None:
            return datos['vendidos_primer_piso'] + datos['vendidos_segundo_piso']
        return None

    importacion = models.ForeignKey(Importacion, on_delete=models.PROTECT, related_name='salidas')
    fila = models.PositiveIntegerField()
    fecha = models.DateField(db_index=True)
    hora = models.TimeField()
    bus = models.CharField(max_length=60)
    origen = models.CharField(max_length=120)
    destino = models.CharField(max_length=120)
    nombre_uno = models.CharField(max_length=180, blank=True)
    nombre_dos = models.CharField(max_length=180, blank=True)
    conductor_uno = models.ForeignKey(Conductor, null=True, blank=True, on_delete=models.PROTECT, related_name='salidas_uno')
    conductor_dos = models.ForeignKey(Conductor, null=True, blank=True, on_delete=models.PROTECT, related_name='salidas_dos')
    correlativo = models.CharField(max_length=100, blank=True)
    anulado = models.BooleanField(default=False)
    clave = models.CharField(max_length=64, db_index=True)
    clave_confirmada = models.CharField(max_length=64, unique=True, null=True, blank=True)
    original = models.JSONField(default=dict)

    class Meta:
        ordering = ['fecha', 'hora', 'fila']
        constraints = [models.UniqueConstraint(fields=['importacion', 'fila'], name='conductores_fila_unica')]


class SituacionConductor(models.Model):
    TIPOS = [('DESCANSO', 'Descanso'), ('VACACIONES', 'Vacaciones'), ('PERMISO', 'Permiso'), ('LICENCIA_CG', 'Licencia con goce'), ('LICENCIA_SG', 'Licencia sin goce'), ('DESCUENTO', 'Descuento'), ('LICENCIA', 'Licencia (registro anterior)')]
    conductor = models.ForeignKey(Conductor, on_delete=models.PROTECT, related_name='situaciones')
    inicio = models.DateField()
    fin = models.DateField()
    tipo = models.CharField(max_length=12, choices=TIPOS)
    motivo = models.CharField(max_length=500, blank=True, default='')
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(fin__gte=models.F('inicio')), name='conductores_periodo_valido')]


class Auditoria(models.Model):
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    mensaje = models.CharField(max_length=500)
    importacion = models.ForeignKey(Importacion, null=True, blank=True, on_delete=models.PROTECT, related_name='historial')
    situacion = models.ForeignKey(SituacionConductor, null=True, blank=True, on_delete=models.PROTECT)
