"""Usa las vistas reales; solo excluye el registro de la API Ninja heredada."""
from django.test import override_settings
with override_settings(MOVIL_HABILITADO=False):
    from .urls import urlpatterns as originales
urlpatterns=list(originales)
