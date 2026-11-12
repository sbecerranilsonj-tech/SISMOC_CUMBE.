# ==============================================================================
# core/models.py
# SISMOC-CUMBE | Modelo de Usuario Personalizado y Matriz de 7 Roles (RBAC)
# Empresa de Transportes El Cumbe S.A.C. — RUC: 20480397731
# ==============================================================================

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


class UsuarioManager(BaseUserManager):
    """Manager personalizado para el modelo Usuario usando DNI o Username."""

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError(_("El nombre de usuario es obligatorio"))
        email = self.normalize_email(email) if email else ''
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("rol", Usuario.Rol.ADMINISTRADOR)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("El superusuario debe tener is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("El superusuario debe tener is_superuser=True."))

        return self.create_user(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """
    Modelo de Usuario extendido con los 7 Roles Oficiales de Transportes El Cumbe S.A.C.
    Definido en el Plan de Prácticas Pre Profesionales (USS - 2026-II).
    """

    class Rol(models.TextChoices):
        GERENTE_GENERAL = "GERENTE_GENERAL", _("👑 Gerente General")
        ADMINISTRADOR = "ADMINISTRADOR", _("⚙️ Administrador del Sistema")
        CONTADORA = "CONTADORA", _("📊 Contadora General")
        CONDUCTOR = "CONDUCTOR", _("🚌 Conductor / Chofer")
        OPERADOR_EMBARQUE = "OPERADOR_EMBARQUE", _("📱 Operador en Bus / Embarcador")
        BOLETERIA = "BOLETERIA", _("🎟️ Vendedor / Boletería")
        ADMINISTRATIVO = "ADMINISTRATIVO", _("👔 Empleado / Personal Administrativo")

    # Identificación Oficial en Perú
    dni = models.CharField(
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        verbose_name="DNI",
        help_text="Documento Nacional de Identidad (8 dígitos)",
    )
    rol = models.CharField(
        max_length=25,
        choices=Rol.choices,
        default=Rol.ADMINISTRATIVO,
        verbose_name="Rol de Usuario (RBAC)",
    )
    telefono = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name="Teléfono / Celular",
    )
    direccion = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Dirección de Domicilio",
    )
    fecha_nacimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de Nacimiento",
    )
    foto = models.ImageField(
        upload_to="usuarios/fotos/",
        blank=True,
        null=True,
        verbose_name="Foto de Perfil / Reconocimiento Facial",
    )

    # Campos específicos para Conductores
    licencia_conducir = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="N° de Licencia de Conducir (MTC)",
        help_text="Requerido para el rol de Conductor (Categoría AIIIC o similar)",
    )
    categoria_licencia = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        default="A-IIIc",
        verbose_name="Categoría de Licencia MTC",
    )

    # Agencia / Sede de asignación principal
    agencia_sede = models.CharField(
        max_length=100,
        blank=True,
        default="Chiclayo - Terminal Central",
        verbose_name="Agencia / Sede Asignada",
        help_text="Chiclayo, Cajamarca, Trujillo, Jaén, Chota, Cutervo, Lima",
    )

    # Código ID en el Reloj Biométrico ZKTeco (Enroll Number)
    turno = models.ForeignKey(
        "asistencia.TurnoHorario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
        verbose_name="Turno Habitual Asignado",
    )
    zkteco_user_id = models.IntegerField(
        blank=True,
        null=True,
        unique=True,
        verbose_name="ID en Reloj Biométrico ZKTeco",
        help_text="Número de usuario registrado en el dispositivo ZKTeco",
    )

    # Estado del personal en la empresa
    esta_activo = models.BooleanField(
        default=True,
        verbose_name="Personal Activo en Planilla",
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro",
    )
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Modificación",
    )

    objects = UsuarioManager()

    class Meta:
        verbose_name = "Usuario SISMOC"
        verbose_name_plural = "Usuarios SISMOC (Personal El Cumbe)"
        ordering = ["last_name", "first_name", "username"]

    def save(self, *args, **kwargs):
        if self.dni == '':
            self.dni = None
        super().save(*args, **kwargs)

    def __str__(self):
        nombre = f"{self.first_name} {self.last_name}".strip()
        if not nombre:
            nombre = self.username
        return f"{nombre} ({self.get_rol_display()}) — DNI: {self.dni}"

    # Helper properties para validación rápida de roles en vistas/servicios
    @property
    def es_gerente(self):
        return self.rol == self.Rol.GERENTE_GENERAL or self.is_superuser

    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMINISTRADOR or self.is_superuser

    @property
    def es_contadora(self):
        return self.rol in [self.Rol.CONTADORA, self.Rol.ADMINISTRADOR, self.Rol.GERENTE_GENERAL] or self.is_superuser

    @property
    def es_conductor(self):
        return self.rol == self.Rol.CONDUCTOR

    @property
    def es_operador(self):
        return self.rol in [self.Rol.OPERADOR_EMBARQUE, self.Rol.CONDUCTOR]

    @property
    def es_boleteria(self):
        return self.rol in [self.Rol.BOLETERIA, self.Rol.ADMINISTRADOR]

    @property
    def nombre_completo(self):
        nombre = f"{self.first_name} {self.last_name}".strip()
        return nombre if nombre else self.username

    @property
    def nombre_corto(self):
        ficha = getattr(self, "ficha_trabajador", None)
        if ficha and ficha.nombres and ficha.apellido_paterno:
            return ficha.nombre_corto
        if self.first_name.strip() and self.last_name.strip():
            return f"{self.last_name.split()[0]} {self.first_name.split()[0]}"
        return self.nombre_completo
