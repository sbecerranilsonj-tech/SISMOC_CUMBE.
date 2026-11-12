# ==============================================================================
# core/schemas.py
# SISMOC-CUMBE | Esquemas Pydantic / Ninja para Autenticación y Usuarios
# ==============================================================================

from typing import Optional, List
from ninja import Schema
from pydantic import Field


class LoginSchema(Schema):
    """Credenciales para inicio de sesión (puede usar username o DNI)."""
    username_or_dni: str = Field(..., description="Nombre de usuario o DNI de 8 dígitos", example="48039773")
    password: str = Field(..., description="Contraseña de acceso", example="cumbe2026")


class UsuarioOutSchema(Schema):
    """Datos públicos y de perfil del usuario."""
    id: int
    dni: str
    username: str
    first_name: str
    last_name: str
    nombre_completo: str
    email: Optional[str] = None
    rol: str
    rol_display: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    agencia_sede: str
    licencia_conducir: Optional[str] = None
    categoria_licencia: Optional[str] = None
    zkteco_user_id: Optional[int] = None
    esta_activo: bool
    foto_url: Optional[str] = None

    @staticmethod
    def resolve_rol_display(obj):
        return obj.get_rol_display()

    @staticmethod
    def resolve_nombre_completo(obj):
        return obj.nombre_completo

    @staticmethod
    def resolve_foto_url(obj):
        if obj.foto:
            return obj.foto.url
        return None


class TokenSchema(Schema):
    """Respuesta con token JWT y perfil del usuario tras login exitoso."""
    access_token: str
    token_type: str = "Bearer"
    user: UsuarioOutSchema


class UsuarioCreateSchema(Schema):
    """Datos para registrar un nuevo colaborador en SISMOC."""
    dni: str = Field(..., min_length=8, max_length=8, description="DNI de 8 dígitos")
    username: str = Field(..., description="Nombre de usuario único para acceso")
    password: str = Field(..., min_length=6, description="Contraseña de acceso")
    first_name: str = Field(..., description="Nombres")
    last_name: str = Field(..., description="Apellidos")
    email: Optional[str] = None
    rol: str = Field(..., description="Uno de los 7 roles válidos")
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    agencia_sede: Optional[str] = "Chiclayo - Terminal Central"
    licencia_conducir: Optional[str] = None
    categoria_licencia: Optional[str] = "A-IIIc"
    zkteco_user_id: Optional[int] = None


class UsuarioUpdateSchema(Schema):
    """Datos actualizables de un colaborador."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    rol: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    agencia_sede: Optional[str] = None
    licencia_conducir: Optional[str] = None
    categoria_licencia: Optional[str] = None
    zkteco_user_id: Optional[int] = None
    esta_activo: Optional[bool] = None


class CambiarPasswordSchema(Schema):
    """Cambio de contraseña por el usuario actual."""
    old_password: str
    new_password: str = Field(..., min_length=6)


class MensajeSchema(Schema):
    """Respuesta estándar para operaciones exitosas."""
    mensaje: str
    exito: bool = True
