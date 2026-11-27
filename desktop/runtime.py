"""Directorios y base separados de cualquier instalación de desarrollo o nube."""
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


def preparar_entorno(data_dir=None):
    root=Path(data_dir) if data_dir else Path(os.environ.get('LOCALAPPDATA',Path.home()))/'SISMOC-CUMBE'/'Escritorio'
    root.mkdir(parents=True,exist_ok=True)
    keyfile=root/'.secret_key'
    try:
        with keyfile.open('x',encoding='utf-8') as f:f.write(secrets.token_urlsafe(64))
    except FileExistsError:
        pass
    key=keyfile.read_text(encoding='utf-8').strip()
    if len(key)<50:raise ValueError('La clave local está dañada. Restaure una copia de seguridad.')
    os.environ.update(SISMOC_EDITION='escritorio',SISMOC_LOAD_DOTENV='False',
        SISMOC_DESKTOP_SECRET=key,SISMOC_DESKTOP_DATA=str(root),DJANGO_SETTINGS_MODULE='config.settings_desktop')
    for sub in ('media','private_bancos','private_conductores','backups','logs'):
        (root/sub).mkdir(exist_ok=True)
    return root


def respaldo_antes_de_migrar(root):
    archivo=Path(root)/'sismoc.sqlite3'
    if not archivo.exists():return None
    target=Path(root)/'backups'/('antes_actualizar_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.sqlite3')
    with closing(sqlite3.connect(archivo)) as source,closing(sqlite3.connect(target)) as dest:
        source.backup(dest)
    return target


def detener_servidor(server,thread=None):
    # Primero finalizar las tareas; cerrar el trigger antes provoca errores de socket.
    from waitress.wasyncore import close_all
    server.task_dispatcher.shutdown(timeout=180)
    close_all(getattr(server,'_map',getattr(server,'map',{})))
    if thread:thread.join(timeout=3)


class InstanciaUnica:
    def __init__(self,root):self.path=Path(root)/'.instance.lock';self.handle=None
    def __enter__(self):
        import msvcrt
        self.handle=self.path.open('a+b');self.handle.seek(0)
        if self.path.stat().st_size==0:self.handle.write(b'0');self.handle.flush()
        self.handle.seek(0)
        try:msvcrt.locking(self.handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            self.handle.close();self.handle=None
            raise RuntimeError('SISMOC ya está abierto. Busque su ventana en la barra de tareas.')
        return self
    def __exit__(self,*exc):
        if self.handle:
            import msvcrt
            self.handle.seek(0);msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1);self.handle.close()
