# ==============================================================================
# core/api.py
# SISMOC-CUMBE | Endpoints de Autenticación, Perfil y Gestión de Usuarios (RBAC)
# ==============================================================================

from typing import List, Optional
from django.contrib.auth import authenticate
from django.db.models import Q
from ninja import Router
from ninja.errors import HttpError

from core.models import Usuario
from core.schemas import (
    LoginSchema,
    TokenSchema,
    UsuarioOutSchema,
    UsuarioCreateSchema,
    UsuarioUpdateSchema,
    CambiarPasswordSchema,
    MensajeSchema,
)
from core.security import create_access_token, auth_any, auth_admin_only, auth_contadora_or_admin

router = Router()


@router.post("/login", response=TokenSchema, auth=None)
def login(request, data: LoginSchema):
    """
    Inicio de sesión para colaboradores de Transportes El Cumbe S.A.C.
    Permite identificarse con Nombre de Usuario o con DNI (8 dígitos).
    Retorna el Token JWT Bearer y el perfil completo con el Rol RBAC asignado.
    """
    identificador = data.username_or_dni.strip()
    password = data.password

    # Buscar usuario por username o por DNI
    try:
        user_obj = Usuario.objects.get(
            Q(username__iexact=identificador) | Q(dni=identificador)
        )
    except Usuario.DoesNotExist:
        raise HttpError(401, "Credenciales incorrectas: Usuario o DNI no encontrado")

    # Autenticar contraseña
    if not user_obj.check_password(password):
        raise HttpError(401, "Credenciales incorrectas: Contraseña no válida")

    if not user_obj.is_active or not user_obj.esta_activo:
        raise HttpError(403, "Su cuenta de colaborador se encuentra inactiva. Contacte al Administrador.")

    # Generar token JWT
    token = create_access_token(user_obj)

    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": user_obj,
    }


@router.get("/me", response=UsuarioOutSchema, auth=auth_any)
def obtener_perfil_actual(request):
    """Obtiene los datos del colaborador actualmente autenticado."""
    return request.auth


@router.post("/cambiar-password", response=MensajeSchema, auth=auth_any)
def cambiar_password(request, data: CambiarPasswordSchema):
    """Permite al usuario autenticado cambiar su contraseña de acceso."""
    user = request.auth
    if not user.check_password(data.old_password):
        raise HttpError(400, "La contraseña actual no es correcta")

    user.set_password(data.new_password)
    user.save()
    return {"mensaje": "Contraseña actualizada exitosamente", "exito": True}


@router.get("/roles", response=List[dict], auth=None)
def listar_roles(request):
    """Retorna la matriz oficial de los 7 Roles RBAC configurados en el sistema."""
    roles = [
        {
            "codigo": Usuario.Rol.GERENTE_GENERAL,
            "nombre": "Gerente General",
            "icono": "👑",
            "descripcion": "Dashboard Ejecutivo, KPIs financieros, ocupación de flota y auditoría global.",
        },
        {
            "codigo": Usuario.Rol.ADMINISTRADOR,
            "nombre": "Administrador del Sistema",
            "icono": "⚙️",
            "descripcion": "Gestión de usuarios, roles RBAC, flota de buses, rutas, agencias y seguridad.",
        },
        {
            "codigo": Usuario.Rol.CONTADORA,
            "nombre": "Contadora General",
            "icono": "📊",
            "descripcion": "Procesador Biométrico ZKTeco, cálculo de HH.EE. 25%/35%, conciliador bancario BCP.",
        },
        {
            "codigo": Usuario.Rol.CONDUCTOR,
            "nombre": "Conductor / Chofer",
            "icono": "🚌",
            "descripcion": "App Móvil, control de ruta GPS, rendición de viáticos/peajes y verificación SUTRAN 8h.",
        },
        {
            "codigo": Usuario.Rol.OPERADOR_EMBARQUE,
            "nombre": "Operador en Bus / Embarcador",
            "icono": "📱",
            "descripcion": "Escaneo QR de boletos en puerta, check-in en paraderos de ruta y croquis dinámico.",
        },
        {
            "codigo": Usuario.Rol.BOLETERIA,
            "nombre": "Vendedor / Boletería",
            "icono": "🎟️",
            "descripcion": "Venta de pasajes en agencia, croquis de 2 pisos, cobros en caja y emisión con QR.",
        },
        {
            "codigo": Usuario.Rol.ADMINISTRATIVO,
            "nombre": "Empleado / Personal Administrativo",
            "icono": "👔",
            "descripcion": "Marcación de asistencia facial/GPS, consulta de horas acumuladas y boletas.",
        },
    ]
    return roles


@router.get("/usuarios", response=List[UsuarioOutSchema], auth=auth_contadora_or_admin)
def listar_usuarios(
    request,
    rol: Optional[str] = None,
    q: Optional[str] = None,
    solo_activos: bool = True,
):
    """
    Lista los colaboradores registrados con filtros opcionales por Rol, búsqueda por nombre/DNI y estado.
    Acceso autorizado para Contadora, Administrador y Gerente General.
    """
    queryset = Usuario.objects.all()

    if solo_activos:
        queryset = queryset.filter(esta_activo=True)

    if rol:
        queryset = queryset.filter(rol=rol)

    if q:
        termino = q.strip()
        queryset = queryset.filter(
            Q(first_name__icontains=termino)
            | Q(last_name__icontains=termino)
            | Q(dni__icontains=termino)
            | Q(username__icontains=termino)
            | Q(licencia_conducir__icontains=termino)
        )

    return list(queryset)


@router.post("/usuarios", response=UsuarioOutSchema, auth=auth_admin_only)
def crear_usuario(request, data: UsuarioCreateSchema):
    """Registra un nuevo colaborador en la plataforma (Solo Administrador / Gerente)."""
    if Usuario.objects.filter(username__iexact=data.username).exists():
        raise HttpError(400, f"El nombre de usuario '{data.username}' ya se encuentra en uso.")

    if Usuario.objects.filter(dni=data.dni).exists():
        raise HttpError(400, f"El DNI '{data.dni}' ya se encuentra registrado.")

    if data.zkteco_user_id and Usuario.objects.filter(zkteco_user_id=data.zkteco_user_id).exists():
        raise HttpError(400, f"El ID de biométrico ZKTeco '{data.zkteco_user_id}' ya pertenece a otro trabajador.")

    nuevo_usuario = Usuario.objects.create_user(
        username=data.username,
        email=data.email,
        password=data.password,
        dni=data.dni,
        first_name=data.first_name,
        last_name=data.last_name,
        rol=data.rol,
        telefono=data.telefono,
        direccion=data.direccion,
        agencia_sede=data.agencia_sede or "Chiclayo - Terminal Central",
        licencia_conducir=data.licencia_conducir,
        categoria_licencia=data.categoria_licencia,
        zkteco_user_id=data.zkteco_user_id,
        esta_activo=True,
    )

    return nuevo_usuario


@router.get("/usuarios/{int:user_id}", response=UsuarioOutSchema, auth=auth_contadora_or_admin)
def obtener_usuario_por_id(request, user_id: int):
    """Obtiene el detalle de un colaborador por su ID."""
    try:
        return Usuario.objects.get(id=user_id)
    except Usuario.DoesNotExist:
        raise HttpError(404, "Colaborador no encontrado")


@router.put("/usuarios/{int:user_id}", response=UsuarioOutSchema, auth=auth_admin_only)
def actualizar_usuario(request, user_id: int, data: UsuarioUpdateSchema):
    """Actualiza los datos de un colaborador (Solo Administrador)."""
    try:
        user_obj = Usuario.objects.get(id=user_id)
    except Usuario.DoesNotExist:
        raise HttpError(404, "Colaborador no encontrado")

    update_fields = data.dict(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(user_obj, field, value)

    user_obj.save()
    return user_obj


@router.delete("/usuarios/{int:user_id}", response=MensajeSchema, auth=auth_admin_only)
def desactivar_usuario(request, user_id: int):
    """Desactiva lógicamente la cuenta de un colaborador (Soft-delete)."""
    try:
        user_obj = Usuario.objects.get(id=user_id)
    except Usuario.DoesNotExist:
        raise HttpError(404, "Colaborador no encontrado")

    user_obj.esta_activo = False
    user_obj.is_active = False
    user_obj.save()

    return {"mensaje": f"El usuario '{user_obj.nombre_completo}' ha sido desactivado.", "exito": True}
