# ==============================================================================
# asistencia/admin.py
# SISMOC-CUMBE | Configuración de Django Admin para Asistencia y Biometría
# ==============================================================================

from django.contrib import admin
from asistencia.forms import TrabajadorForm
from asistencia.models import (
    TurnoHorario,
    MarcacionBiometrica,
    ResumenAsistenciaDiaria,
    CargaArchivoAsistencia,
    IdentidadBiometrica,
    Trabajador,
)


@admin.register(Trabajador)
class TrabajadorAdmin(admin.ModelAdmin):
    form = TrabajadorForm
    list_display = ("codigo", "nombre_corto", "dni", "area", "sede")
    search_fields = ("identidades__codigo", "nombre_completo", "dni", "area")
    readonly_fields = ("codigo", "creado_el", "nombre_completo")


@admin.register(IdentidadBiometrica)
class IdentidadBiometricaAdmin(admin.ModelAdmin):
    list_display = ("sede", "equipo", "codigo", "nombre", "usuario")
    search_fields = ("codigo", "nombre", "sede")
    list_filter = ("sede",)
    # La pantalla de importación realiza la asociación con su historial y marcaciones.
    readonly_fields = ("sede", "equipo", "codigo", "nombre", "usuario", "trabajador")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TurnoHorario)
class TurnoHorarioAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "hora_entrada",
        "hora_salida",
        "tolerancia_minutos",
        "es_para_conductores",
        "activo",
    )
    list_filter = ("es_para_conductores", "activo")
    search_fields = ("nombre",)


@admin.register(MarcacionBiometrica)
class MarcacionBiometricaAdmin(admin.ModelAdmin):
    list_display = (
        "dni",
        "nombre_empleado",
        "fecha_hora",
        "tipo_evento",
        "origen",
        "dispositivo_ip",
        "es_valida",
    )
    list_filter = ("tipo_evento", "origen", "es_valida", "fecha_hora")
    search_fields = ("dni", "nombre_empleado", "dispositivo_ip")
    date_hierarchy = "fecha_hora"
    ordering = ("-fecha_hora",)


@admin.register(ResumenAsistenciaDiaria)
class ResumenAsistenciaDiariaAdmin(admin.ModelAdmin):
    readonly_fields = ("verificado_contabilidad", "estado_revision", "revisado_por", "fecha_revision")
    list_display = (
        "fecha",
        "usuario",
        "estado",
        "primera_entrada",
        "ultima_salida",
        "minutos_tardanza",
        "horas_trabajadas",
        "horas_extras_25",
        "horas_extras_35",
        "vueltas_codigo",
        "total_vueltas_num",
        "verificado_contabilidad",
    )
    list_filter = (
        "estado",
        "verificado_contabilidad",
        "vueltas_codigo",
        "fecha",
        "usuario__rol",
    )
    search_fields = (
        "usuario__dni",
        "usuario__first_name",
        "usuario__last_name",
        "observaciones",
    )
    date_hierarchy = "fecha"
    ordering = ("-fecha", "usuario__last_name")


@admin.register(CargaArchivoAsistencia)
class CargaArchivoAsistenciaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_archivo_original",
        "mes_periodo",
        "fecha_subida",
        "subido_por",
        "total_filas_procesadas",
        "total_empleados_identificados",
        "total_horas_extras_25",
        "total_horas_extras_35",
        "total_vueltas_conductores",
        "estado",
    )
    list_filter = ("estado", "mes_periodo", "fecha_subida")
    search_fields = ("nombre_archivo_original", "mes_periodo")
    ordering = ("-fecha_subida",)
