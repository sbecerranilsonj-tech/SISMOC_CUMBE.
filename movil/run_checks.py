"""Ejecutor independiente para entornos donde Ninja no está disponible."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
packages = root / 'venv' / 'Lib' / 'site-packages'
if packages.exists():
    sys.path.append(str(packages))
os.environ['DJANGO_SETTINGS_MODULE'] = 'movil.test_settings'
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py', 'test', 'movil', *sys.argv[1:]])
