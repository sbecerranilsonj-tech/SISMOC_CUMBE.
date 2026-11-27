"""Mantener módulos de gestión y excluir los servicios móviles de esta edición."""
from django.urls import URLPattern, URLResolver
from .urls import urlpatterns as originales

urlpatterns=[p for p in originales
    if not str(p.pattern).startswith(('movil/','api/'))
    and not (getattr(p,'name','') or '').startswith('movil_')]
