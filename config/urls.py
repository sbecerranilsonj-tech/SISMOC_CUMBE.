# ==============================================================================
# config/urls.py
# SISMOC-CUMBE | Enrutador Principal de URLs
# Empresa de Transportes El Cumbe S.A.C. - RUC: 20480397731
# ==============================================================================

from django.contrib import admin
from django.urls import path, include, re_path
from core.deployment import health, archivo_media
from django.conf import settings
from django.conf.urls.static import static
from config.api import api
from core.views import dashboard_view, login_view, logout_view
from asistencia import views as asistencia_views
from asistencia import views_trabajadores
from asistencia import views_revision_trabajador
from asistencia import views_horarios
from asistencia import views_personal
from asistencia import views_reglas
from core.views_prototipos import prototipos_iq2
from bancos import views as bancos_views
from conductores import views as conductores_views

urlpatterns = [
    path('health/',health,name='health'),
    path('movil/', include('movil.urls')),
    path('conductores/salidas/<int:pk>/resolver/', conductores_views.resolver_salida, name='conductores_resolver_salida'),
    path('conductores/calendario/excel/', conductores_views.exportar_calendario, name='conductores_exportar_calendario'),
    path('conductores/dia/situacion/', conductores_views.situacion_dia, name='conductores_situacion_dia'),
    path('conductores/ficha/', conductores_views.ficha, name='conductores_ficha'),
    path('conductores/fichas/', conductores_views.catalogo, name='conductores_catalogo'),
    path('conductores/configuracion/', conductores_views.configuracion, name='conductores_configuracion'),
    path('conductores/', conductores_views.importar, name='conductores_importar'),
    path('conductores/validacion/', conductores_views.validacion, name='conductores_validacion'),
    path('conductores/control/', conductores_views.control, name='conductores_control'),
    path('conductores/reportes/<int:pk>/', conductores_views.detalle, name='conductores_detalle'),
    path('conductores/reportes/<int:pk>/archivo/', conductores_views.documento, name='conductores_documento'),
    path('conductores/situaciones/<int:pk>/anular/', conductores_views.anular_situacion, name='conductores_anular_situacion'),
    path('bancos/estados/<int:pk>/diagnostico/', bancos_views.diagnostico, name='bancos_diagnostico'),
    path('bancos/', bancos_views.panel, name='bancos_importar'),
    path('bancos/validacion/', bancos_views.validacion, name='bancos_validacion'),
    path('bancos/control/', bancos_views.control, name='bancos_control'),
    path('bancos/estados/<int:pk>/', bancos_views.detalle, name='bancos_detalle'),
    path('bancos/estados/<int:pk>/pdf/', bancos_views.documento, name='bancos_pdf'),
    path('personal/<int:trabajador_id>/guardar/', views_personal.guardar_personal, name='guardar_personal'),
    path("prototipos/iq2/", prototipos_iq2, name="prototipos_iq2"),
    path('asistencia/reglas-jornada/', views_reglas.reglas_jornada, name='reglas_jornada'),
    path("asistencia/codigos/sugerencias/", views_trabajadores.sugerir_codigos, name="sugerir_codigos"),
    path("asistencia/trabajadores/<int:trabajador_id>/editar/", views_trabajadores.editar_trabajador, name="editar_ficha_trabajador"),
    path("asistencia/registrar-trabajo-omitido/", views_revision_trabajador.registrar_trabajo_omitido, name="registrar_trabajo_omitido"),
    path("asistencia/horarios/", views_horarios.horarios, name="programar_horarios"),
    path("asistencia/aprobar-periodo-trabajador/", views_revision_trabajador.aprobar_periodo_trabajador, name="aprobar_periodo_trabajador"),
    path("asistencia/registrar-dia-sin-marcas/", views_revision_trabajador.registrar_dia_sin_marcas, name="registrar_dia_sin_marcas"),
    path("asistencia/validar-marcaciones-trabajador/", views_revision_trabajador.validar_marcaciones_trabajador, name="validar_marcaciones_trabajador"),
    path("asistencia/enviar-importadas/", views_trabajadores.enviar_a_asistencia, name="enviar_a_asistencia"),
    path("asistencia/trabajadores/buscar/", views_trabajadores.buscar_trabajadores, name="buscar_trabajadores"),
    path("asistencia/identidad/<int:identidad_id>/confirmar/", views_trabajadores.confirmar_trabajador, name="confirmar_trabajador"),
    path("asistencia/identidad/<int:identidad_id>/registrar/", views_trabajadores.registrar_trabajador, name="registrar_trabajador"),
    path("asistencia/identidad/<int:identidad_id>/editar/", views_trabajadores.editar_trabajador, name="editar_trabajador"),
    # Dashboard Web Principal (Sprint 1)
    path("", dashboard_view, name="dashboard"),

    # Autenticacion Institucional y Cierre de Sesion (7 Roles RBAC)
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("asistencia/jornada/<int:resumen_id>/", asistencia_views.accion_jornada, name="accion_jornada"),
    path("asistencia/marcacion/<int:marcacion_id>/asociar/", asistencia_views.asociar_marcacion, name="asociar_marcacion"),
    path("asistencia/exportar/", asistencia_views.exportar_asistencia, name="exportar_asistencia"),
    path("asistencia/cerrar-periodo/", asistencia_views.cerrar_periodo, name="cerrar_periodo"),
    path("asistencia/crear-jornada/", asistencia_views.crear_jornada, name="crear_jornada"),
    path("asistencia/consultar-huellero/", asistencia_views.consultar_huellero, name="consultar_huellero"),
    path("asistencia/registros-huellero/", asistencia_views.registros_huellero, name="registros_huellero"),
    path("asistencia/importar/", asistencia_views.importar_excel_web, name="importar_excel_web"),
    path("asistencia/identidad/<int:identidad_id>/", asistencia_views.vincular_identidad, name="vincular_identidad"),
    path("asistencia/marcar/", asistencia_views.marcar_web, name="marcar_web"),

    # Panel de Administracion de Django
    path("admin/", admin.site.urls),

    # API REST con Django Ninja (Documentacion interactiva en /api/docs)
    path("api/", api.urls),
]

# Servir archivos media en desarrollo (fotos de peajes, archivos Excel)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [re_path(r'^media/(?P<path>.+)$',archivo_media,name='archivo_media')]
