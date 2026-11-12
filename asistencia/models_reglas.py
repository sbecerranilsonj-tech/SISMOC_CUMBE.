from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class ReglaJornada(models.Model):
    """Versiones con vigencia: la configuración nueva no reemplaza la anterior."""
    area = models.CharField(max_length=100, blank=True, help_text="Vacío: regla general.")
    trabajador = models.ForeignKey('asistencia.Trabajador', null=True, blank=True, on_delete=models.PROTECT)
    desde = models.DateField()
    hasta = models.DateField(null=True, blank=True)
    minutos_diarios = models.PositiveIntegerField(default=480, validators=[MinValueValidator(1), MaxValueValidator(1440)])
    minutos_sabado = models.PositiveIntegerField(default=240, validators=[MinValueValidator(1), MaxValueValidator(1440)])
    minutos_refrigerio = models.PositiveIntegerField(default=45, validators=[MaxValueValidator(180)])
    exento_marcacion = models.BooleanField(default=False)
    motivo = models.CharField(max_length=500)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creado_el = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-desde', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(hasta__isnull=True) | models.Q(hasta__gte=models.F('desde')), name='regla_vigencia_valida')]


class PeriodoVacaciones(models.Model):
    trabajador = models.ForeignKey('asistencia.Trabajador', on_delete=models.CASCADE, related_name='periodos_vacaciones')
    desde = models.DateField()
    hasta = models.DateField()
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    creado_el = models.DateTimeField(auto_now_add=True)
    aprobado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    aprobado_el = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-desde', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(hasta__gte=models.F('desde')), name='vacaciones_vigencia_valida')]

    @property
    def total_dias(self):
        return (self.hasta - self.desde).days + 1


class DescansoProgramado(models.Model):
    sin_trabajo_programado = models.BooleanField(default=False)
    trabajador = models.ForeignKey('asistencia.Trabajador', on_delete=models.CASCADE, related_name='descansos_programados')
    desde = models.DateField()
    hasta = models.DateField()
    dias = models.JSONField(default=list)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creado_el = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_el', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(hasta__gte=models.F('desde')), name='descanso_vigencia_valida')]


class DiaEspecial(models.Model):
    fecha = models.DateField(unique=True)
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=12, choices=[('EMPRESA', 'Día especial de empresa'), ('NACIONAL', 'Feriado nacional')], default='EMPRESA')
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creado_el = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha']
