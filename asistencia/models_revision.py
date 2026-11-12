"""Evidencias y decisiones de revisión, separadas de las marcas originales."""
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class IncidenciaAsistencia(models.Model):
    TIPOS = [
        ("SIN_PROGRAMACION", "Sin trabajo programado"),
        ("DESCANSO_SEMANAL", "Descanso semanal"), ("FERIADO_NO_LABORADO", "Feriado no laborado"),
        ("NO_LABORO", "No laboró"),
        ("VACACIONES", "Vacaciones"), ("PERMISO", "Permiso"), ("CUMPLEANOS", "Cumpleaños"),
        ("DESCANSO_MEDICO", "Descanso médico"), ("CAMBIO_DESCANSO", "Cambio de descanso"),
        ("COBERTURA", "Cobertura de compañero"), ("FERIADO", "Feriado o descanso trabajado"),
        ("MARCACION_INCOMPLETA", "Marcación incompleta"), ("OTRO", "Otra justificación"),
    ]
    resumen = models.ForeignKey("asistencia.ResumenAsistenciaDiaria", on_delete=models.CASCADE, related_name="incidencias")
    tipo = models.CharField(max_length=24, choices=TIPOS)
    motivo = models.TextField()
    minutos = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(1440)])
    evidencia_url = models.URLField(blank=True, max_length=500)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="incidencias_registradas")
    creado_el = models.DateTimeField(auto_now_add=True)
    aprobado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="incidencias_aprobadas")
    aprobado_el = models.DateTimeField(null=True, blank=True)


class AjusteAsistencia(models.Model):
    CONCEPTOS = [
        ("horas_trabajadas", "Horas efectivas"), ("horas_extras_25", "Extras 25 %"),
        ("horas_extras_35", "Extras 35 %"), ("horas_nocturnas", "Horas nocturnas"),
        ("descanso_feriado", "Descanso o feriado trabajado"),
        ("descuento", "Descuento de tiempo"), ("compensacion", "Compensación de tiempo"),
    ]
    resumen = models.ForeignKey("asistencia.ResumenAsistenciaDiaria", on_delete=models.CASCADE, related_name="ajustes")
    concepto = models.CharField(max_length=24, choices=CONCEPTOS)
    minutos = models.IntegerField(validators=[MinValueValidator(-1440), MaxValueValidator(1440)])
    motivo = models.TextField()
    fecha_origen = models.DateField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="ajustes_registrados")
    creado_el = models.DateTimeField(auto_now_add=True)
    aprobado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ajustes_aprobados")
    aprobado_el = models.DateTimeField(null=True, blank=True)


class RevisionAsistencia(models.Model):
    resumen = models.ForeignKey("asistencia.ResumenAsistenciaDiaria", null=True, blank=True, on_delete=models.SET_NULL, related_name="historial_revision")
    marcacion = models.ForeignKey("asistencia.MarcacionBiometrica", null=True, blank=True, on_delete=models.SET_NULL)
    accion = models.CharField(max_length=50)
    detalle = models.TextField(blank=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]


class CorreccionEvento(models.Model):
    marcacion = models.OneToOneField("asistencia.MarcacionBiometrica", on_delete=models.CASCADE, related_name="correccion_evento")
    tipo_evento = models.CharField(max_length=20)
    motivo = models.TextField()
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    fecha = models.DateTimeField(auto_now=True)


class CierreAsistencia(models.Model):
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    cerrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    cerrado_el = models.DateTimeField(auto_now_add=True)
    total_jornadas = models.PositiveIntegerField()
    resumen_cierre = models.JSONField(default=dict)

    class Meta:
        ordering = ["-fecha_fin"]
        constraints = [models.UniqueConstraint(fields=["fecha_inicio", "fecha_fin"], name="asistencia_cierre_periodo_unico")]
