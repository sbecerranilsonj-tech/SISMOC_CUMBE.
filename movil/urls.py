from django.urls import path
from . import views
from .panel import panel, estados_acceso
from .busqueda import sugerencias_personas
from .ventas import ventas
from .asistencia_diaria import revisar_marca_diaria

urlpatterns = [path('asistencia/<int:pk>/marca/',revisar_marca_diaria,name='movil_revisar_marca_diaria'),path('ventas/',ventas,name='movil_ventas'),path('',panel,name='movil_panel'),path('personas/sugerencias/',sugerencias_personas,name='movil_sugerencias_personas'),path('accesos/estados/',estados_acceso,name='movil_estados_acceso'),path('api/<str:accion>/', views.api, name='movil_api')]

