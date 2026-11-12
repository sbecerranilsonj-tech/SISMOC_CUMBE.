from django.contrib import admin
from .models import Perfil, Zona, Comision, Registro, Solicitud, Operacion, ReglaDescanso, Pago, Incidencia, Pasajero, Auditoria

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'usuario', 'activo', 'activado', 'requiere_rostro']
    search_fields = ['codigo', 'usuario__first_name', 'usuario__dni']
    readonly_fields = ['codigo', 'rostro', 'activacion_hash', 'activacion_hasta']
    actions = ['desvincular']
    @admin.action(description='Desvincular celular y cerrar sesiones')
    def desvincular(self, request, queryset):
        for p in queryset:
            p.dispositivo = ''; p.save(update_fields=['dispositivo'])
            p.sesion_set.update(activa=False)
            Auditoria.objects.create(actor=request.user,accion='Dispositivo desvinculado',detalle={'perfil':p.pk})

@admin.register(Auditoria, Registro)
class SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

for model in [Zona, Comision, Solicitud, Operacion, ReglaDescanso, Pago, Incidencia, Pasajero]:
    admin.site.register(model)

from django.conf import settings
from django.apps import apps
if not getattr(settings,'MOVIL_HABILITADO',True):
    for model in apps.get_app_config('movil').get_models():
        if admin.site.is_registered(model):admin.site.unregister(model)
