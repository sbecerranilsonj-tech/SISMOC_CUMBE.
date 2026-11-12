# ==============================================================================
# core/admin.py
# SISMOC-CUMBE | Panel de Administración de Django para Usuarios y Roles
# ==============================================================================

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from core.models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = (
        "dni",
        "username",
        "first_name",
        "last_name",
        "rol",
        "agencia_sede",
        "zkteco_user_id",
        "licencia_conducir",
        "esta_activo",
        "is_staff",
    )
    list_filter = ("rol", "esta_activo", "agencia_sede", "is_staff")
    search_fields = ("dni", "username", "first_name", "last_name", "email", "licencia_conducir")
    ordering = ("last_name", "first_name")

    fieldsets = (
        ("Credenciales de Acceso", {"fields": ("username", "password")}),
        (
            "Información Personal y Laboral",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "dni",
                    "email",
                    "telefono",
                    "direccion",
                    "fecha_nacimiento",
                    "foto",
                )
            },
        ),
        (
            "Asignación de Rol y Operación SISMOC",
            {
                "fields": (
                    "rol",
                    "agencia_sede",
                    "zkteco_user_id",
                    "licencia_conducir",
                    "categoria_licencia",
                )
            },
        ),
        (
            "Permisos y Estado del Colaborador",
            {
                "fields": (
                    "esta_activo",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Auditoría del Sistema", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            "Registro de Nuevo Colaborador El Cumbe",
            {
                "classes": ("wide",),
                "fields": (
                    "dni",
                    "username",
                    "first_name",
                    "last_name",
                    "rol",
                    "agencia_sede",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
