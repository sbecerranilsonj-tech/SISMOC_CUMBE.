"""Inicio del contenedor de Railway; jamás carga datos locales ni demostraciones."""
import os
from pathlib import Path
import subprocess
import sys

os.chdir(Path(__file__).resolve().parent.parent)
os.environ.setdefault('DEBUG', 'False')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

def main():
    port = int(os.environ.get('PORT', '8000'))
    if not 1 <= port <= 65535:
        raise ValueError('PORT inválido.')
    for command in (['check'], ['migrate','--noinput'], ['bootstrap_admin'], ['collectstatic','--noinput']):
        subprocess.run([sys.executable,'manage.py',*command], check=True)
    import django
    django.setup()
    from django.conf import settings
    for path in (settings.MEDIA_ROOT, settings.PRIVATE_BANCOS_ROOT, settings.PRIVATE_CONDUCTORES_ROOT):
        Path(path).mkdir(parents=True,exist_ok=True)
    os.execvp('gunicorn', ['gunicorn','config.wsgi:application','--bind',f'0.0.0.0:{port}',
        '--workers','1','--worker-class','gthread','--threads','4','--timeout','180',
        '--access-logfile','-','--error-logfile','-'])

if __name__=='__main__':
    main()
