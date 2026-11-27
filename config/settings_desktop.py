"""Configuración exclusiva de la aplicación local; no usa datos ni secretos Railway."""
import hashlib
import os
from pathlib import Path

os.environ['SISMOC_EDITION']='escritorio'
os.environ['SISMOC_LOAD_DOTENV']='False'
from .settings import *

DEBUG=False
ESCRITORIO=True
MOVIL_HABILITADO=False
INSTALLED_APPS=[app for app in INSTALLED_APPS if app!='ninja']
ROOT_URLCONF='config.urls_desktop'
SECRET_KEY=os.environ.get('SISMOC_DESKTOP_SECRET','')
if len(SECRET_KEY)<50:
    raise ImproperlyConfigured('Inicie SISMOC con desktop/launcher.py para cargar la clave local.')
JWT_SIGNING_KEY = hashlib.sha256((SECRET_KEY + '|jwt').encode()).hexdigest()
DATA_DIR=Path(os.environ.get('SISMOC_DESKTOP_DATA',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'SISMOC-CUMBE'/'Escritorio')))
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':str(DATA_DIR/'sismoc.sqlite3'),'OPTIONS':{'timeout':30}}}
MEDIA_ROOT=DATA_DIR/'media'
PRIVATE_BANCOS_ROOT=DATA_DIR/'private_bancos'
PRIVATE_CONDUCTORES_ROOT=DATA_DIR/'private_conductores'
STATIC_ROOT=DATA_DIR/'staticfiles'
ALLOWED_HOSTS=['127.0.0.1','localhost','[::1]']
CSRF_TRUSTED_ORIGINS=[]
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_NAME='sismoc_escritorio_session'
CSRF_COOKIE_NAME='sismoc_escritorio_csrf'
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=[]
SECURE_HSTS_SECONDS=0
SECURE_CONTENT_TYPE_NOSNIFF=True
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
          'staticfiles':{'BACKEND':'whitenoise.storage.CompressedStaticFilesStorage'}}
if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
    MIDDLEWARE.insert(1,'whitenoise.middleware.WhiteNoiseMiddleware')
