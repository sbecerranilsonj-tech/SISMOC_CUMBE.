"""Pruebas de gestión y app sobre SQLite, sin depender de una instalación externa."""
from .settings import *
INSTALLED_APPS=[app for app in INSTALLED_APPS if app!='ninja']
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}
ROOT_URLCONF='config.test_urls'
PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
ALLOWED_HOSTS=['testserver','localhost','127.0.0.1']
SILENCED_SYSTEM_CHECKS=['fields.E210']
