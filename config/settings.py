# ==============================================================================
# config/settings.py
# SISMOC-CUMBE | Configuración Principal de Django
# Empresa de Transportes El Cumbe S.A.C. — RUC: 20480397731
# ==============================================================================

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Directorio base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables de entorno desde .env
if os.getenv('SISMOC_LOAD_DOTENV','True').lower() in ('true','1','yes'):
    load_dotenv(BASE_DIR / ".env")

# Seguridad
SECRET_KEY = os.getenv("SECRET_KEY", "")
JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", "")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('Configure SECRET_KEY con al menos 50 caracteres aleatorios.')
if len(JWT_SIGNING_KEY) < 32:
    raise ImproperlyConfigured('Configure JWT_SIGNING_KEY con al menos 32 caracteres aleatorios.')
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
ESCRITORIO = os.getenv('SISMOC_EDITION', 'demostracion') == 'escritorio'
MOVIL_HABILITADO = not ESCRITORIO
SISMOC_DESCANSO_PUBLICACION_HABILITADA = (
    os.getenv('SISMOC_DESCANSO_PUBLICACION_HABILITADA', 'False').lower()
    in ('true', '1', 'yes')
)
if not DEBUG and not ESCRITORIO:
    ALLOWED_HOSTS += [h for h in (os.getenv('RAILWAY_PUBLIC_DOMAIN'), os.getenv('RAILWAY_PRIVATE_DOMAIN')) if h]
    if os.getenv('RAILWAY_ENVIRONMENT_ID'):
        ALLOWED_HOSTS.append('healthcheck.railway.app')
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Configure ALLOWED_HOSTS con el dominio de la aplicación, sin comodín.')

CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.getenv('CSRF_TRUSTED_ORIGINS','').split(',') if v.strip()]
if os.getenv('RAILWAY_PUBLIC_DOMAIN'):
    CSRF_TRUSTED_ORIGINS.append('https://' + os.environ['RAILWAY_PUBLIC_DOMAIN'])
if not DEBUG and not ESCRITORIO:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # Solo se fuerza HTTPS cuando hay proxy/cloud; el servidor local es HTTP.
    SECURE_SSL_REDIRECT = bool(os.getenv('RAILWAY_ENVIRONMENT_ID')) or \
        os.getenv('SISMOC_FORCE_HTTPS', 'False').lower() in ('true', '1', 'yes')
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_CONTENT_TYPE_NOSNIFF = True


# ==============================================================================
# APLICACIONES INSTALADAS
# ==============================================================================
INSTALLED_APPS = [
    # Django Core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Terceros
    "corsheaders",
    "ninja",

    # Apps del Proyecto SISMOC-CUMBE
    "core.apps.CoreConfig",
    "asistencia.apps.AsistenciaConfig",
    "bancos.apps.BancosConfig",
    "conductores.apps.ConductoresConfig",
    "movil.apps.MovilConfig",
]


# ==============================================================================
# MIDDLEWARE
# ==============================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.GerenteSoloConsultaMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if not DEBUG:
    MIDDLEWARE.insert(1,'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = "config.urls"


# ==============================================================================
# TEMPLATES
# ==============================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context.edicion",
                "config.context.solicitudes_notificacion",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ==============================================================================
# BASE DE DATOS
# ==============================================================================
DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", str(BASE_DIR / "sismoc_cumbe_db.sqlite3")),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
    }
}


# ==============================================================================
# MODELO DE USUARIO PERSONALIZADO (RBAC 7 Roles)
# ==============================================================================
if os.getenv('DATABASE_URL') and not ESCRITORIO:
    import dj_database_url
    DATABASES['default'] = dj_database_url.parse(os.environ['DATABASE_URL'], conn_max_age=60, conn_health_checks=True)
if not DEBUG and not ESCRITORIO and DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    raise ImproperlyConfigured('Configure DATABASE_URL de PostgreSQL para producción.')

AUTH_USER_MODEL = "core.Usuario"


# ==============================================================================
# VALIDACIÓN DE CONTRASEÑAS
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ==============================================================================
# INTERNACIONALIZACIÓN (Perú)
# ==============================================================================
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True


# ==============================================================================
# ARCHIVOS ESTÁTICOS Y MEDIA (Subida de Excel y Fotos de Peajes)
# ==============================================================================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DATA_DIR = Path(os.getenv('DATA_DIR', str(BASE_DIR)))
MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR / 'media'
PRIVATE_BANCOS_ROOT = DATA_DIR / 'private_bancos'
PRIVATE_CONDUCTORES_ROOT = DATA_DIR / 'private_conductores'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage' if not DEBUG else 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


# ==============================================================================
# CONFIGURACIÓN DE DJANGO NINJA (API)
# ==============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==============================================================================
# CORS (Para permitir conexión desde la App Móvil / PWA)
# ==============================================================================
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Solo en desarrollo
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


# ==============================================================================
# CONFIGURACIÓN DEL HUELLERO ZKTECO
# ==============================================================================
ZKTECO_CONFIG = {
    "IP": os.getenv("HUELLERO_IP") or os.getenv("ZKTECO_IP", "192.168.10.202"),
    "PORT": int(os.getenv("ZKTECO_PORT", "4370")),
    "TIMEOUT": 5,  # Segundos de espera para conexión
    "DEVICE_NUMBER": int(os.getenv("ZKTECO_DEVICE_NUMBER", "1")),
    "COMM_KEY": int(os.getenv("ZKTECO_COMM_KEY", "0")),
    "SERIE": os.getenv("ZKTECO_SERIE", "AEWD195060148"),
    "MODELO": "MB360",
}

# Token compartido con el agente que corre en la PC de la sede. Sin él, el
# agente no puede subir marcaciones ni consultar órdenes.
HUELLERO_AGENT_TOKEN = os.getenv("HUELLERO_AGENT_TOKEN", "")
HUELLERO_AGENT_INTERVALO = int(os.getenv("HUELLERO_AGENT_INTERVALO", "30"))

try:
    HUELLERO_AGENTES = json.loads(os.getenv("HUELLERO_AGENTES", "{}") or "{}")
except (ValueError, TypeError):
    HUELLERO_AGENTES = {}
if not isinstance(HUELLERO_AGENTES, dict):
    HUELLERO_AGENTES = {}

# Ventanas de refrigerio del aviso interno. Las marcas fuera de estas ventanas
# se conservan y se marcan como observación; nunca se descuentan automáticamente.
HUELLERO_REFRIGERIO = {
    "manana": ("07:15", "08:00"),
    "tarde": ("18:00", "18:45"),
}


# ==============================================================================
# AUTENTICACIÓN Y REDIRECCIÓN DE SESIÓN
# ==============================================================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
