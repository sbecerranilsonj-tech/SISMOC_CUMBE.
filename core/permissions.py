"""Políticas comunes de lectura y escritura por rol."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from .models import ROLES_GESTION


def acceso_gestion(mensaje):
    """Decorador de solo gestión para vistas HTML; `mensaje` es específico del módulo."""
    def decorador(vista):
        @login_required
        @wraps(vista)
        def protegida(request, *args, **kwargs):
            usuario = request.user
            if (not usuario.is_active or not usuario.esta_activo
                    or not (usuario.is_superuser or usuario.rol in ROLES_GESTION)):
                return HttpResponseForbidden(mensaje)
            return vista(request, *args, **kwargs)
        return protegida
    return decorador



def solo_consulta(usuario):
    # El rol prevalece incluso si la cuenta tiene is_staff/is_superuser.
    return bool(usuario and getattr(usuario, 'is_authenticated', False)
                and getattr(usuario, 'rol', '') == 'GERENTE_GENERAL')


MENSAJE_SOLO_CONSULTA = (
    'Gerente General tiene acceso de solo consulta. No puede modificar registros.'
)
