# ==============================================================================
# core/security.py
# SISMOC-CUMBE | Autenticación Segura con JWT y Autorización RBAC
# ==============================================================================

import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from django.conf import settings
from ninja.security import HttpBearer
from core.models import Usuario


JWT_SECRET_KEY = getattr(settings, "SECRET_KEY", "sismoc-cumbe-jwt-secret-key-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24  # 24 horas de vigencia para el token


def create_access_token(usuario: Usuario) -> str:
    """Genera un token JWT firmado para el usuario con sus datos y rol."""
    ahora = datetime.now(timezone.utc)
    expiracion = ahora + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "sub": str(usuario.id),
        "dni": usuario.dni,
        "username": usuario.username,
        "nombre_completo": usuario.nombre_completo,
        "rol": usuario.rol,
        "email": usuario.email or "",
        "agencia_sede": usuario.agencia_sede,
        "iat": ahora,
        "exp": expiracion,
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica y valida la firma y expiración del token JWT."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


class AuthBearer(HttpBearer):
    """
    Autenticador Bearer para Django Ninja.
    Valida el token JWT en el encabezado 'Authorization: Bearer <token>'
    y adjunta el objeto Usuario a request.auth.
    """

    def __init__(self, roles_permitidos: Optional[List[str]] = None):
        super().__init__()
        self.roles_permitidos = roles_permitidos

    def authenticate(self, request, token):
        payload = decode_access_token(token)
        if not payload:
            return None

        try:
            usuario = Usuario.objects.get(id=int(payload["sub"]), esta_activo=True)
        except Usuario.DoesNotExist:
            return None

        # Si se especificaron roles permitidos, verificar que el usuario tenga uno de ellos
        if self.roles_permitidos:
            if usuario.rol not in self.roles_permitidos and not usuario.is_superuser:
                return None

        return usuario


# Instancias reutilizables de AuthBearer por nivel de acceso
auth_any = AuthBearer()
auth_admin_only = AuthBearer(roles_permitidos=[Usuario.Rol.ADMINISTRADOR, Usuario.Rol.GERENTE_GENERAL])
auth_contadora_or_admin = AuthBearer(roles_permitidos=[Usuario.Rol.CONTADORA, Usuario.Rol.ADMINISTRADOR, Usuario.Rol.GERENTE_GENERAL])
auth_conductor = AuthBearer(roles_permitidos=[Usuario.Rol.CONDUCTOR, Usuario.Rol.ADMINISTRADOR])
auth_operador = AuthBearer(roles_permitidos=[Usuario.Rol.OPERADOR_EMBARQUE, Usuario.Rol.CONDUCTOR, Usuario.Rol.ADMINISTRADOR])
auth_boleteria = AuthBearer(roles_permitidos=[Usuario.Rol.BOLETERIA, Usuario.Rol.ADMINISTRADOR])
