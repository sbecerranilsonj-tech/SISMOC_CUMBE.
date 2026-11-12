# asistencia/apps.py
# SISMOC-CUMBE | Configuración de la app de Asistencia

from django.apps import AppConfig


class AsistenciaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "asistencia"
    verbose_name = "Control de Asistencia y Biometría ZKTeco"

    def ready(self):
        from asistencia import signals  # noqa: F401
