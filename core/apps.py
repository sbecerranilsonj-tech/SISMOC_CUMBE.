# core/apps.py
# Configuración de la app Core (Autenticación y Roles).

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core — Autenticación, Usuarios y Roles RBAC"
