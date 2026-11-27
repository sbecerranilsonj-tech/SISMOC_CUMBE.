"""Pruebas de gestión y app sobre SQLite, sin depender de una instalación externa."""
from .settings import *
SECRET_KEY = 'test-only-secret-key-' * 4
JWT_SIGNING_KEY = 'test-only-jwt-signing-key-' * 4
INSTALLED_APPS=[app for app in INSTALLED_APPS if app!='ninja']
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}
ROOT_URLCONF='config.test_urls'
PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
ALLOWED_HOSTS=['testserver','localhost','127.0.0.1']
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_SECONDS=0
SILENCED_SYSTEM_CHECKS=['fields.E210']
