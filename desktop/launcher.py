"""SISMOC en ventana Windows, servidor local embebido y datos persistentes."""
import sys
import logging
from pathlib import Path
from threading import Thread

BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
sys.path.insert(0,str(BASE))
from desktop.runtime import preparar_entorno,InstanciaUnica,respaldo_antes_de_migrar,detener_servidor


def main():
    root=preparar_entorno()
    logging.basicConfig(filename=root/'logs'/'sismoc.log',level=logging.WARNING,encoding='utf-8')
    with InstanciaUnica(root):
        import django
        django.setup()
        from django.core.management import call_command
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor=MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            respaldo_antes_de_migrar(root)
            call_command('migrate',interactive=False,verbosity=0)
        from desktop.first_run import crear_cuenta_inicial
        if not crear_cuenta_inicial():return
        call_command('collectstatic',interactive=False,verbosity=0)
        from django.core.wsgi import get_wsgi_application
        from waitress import create_server
        import webview
        webview.settings['ALLOW_DOWNLOADS']=True
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER']=False
        server=create_server(get_wsgi_application(),host='127.0.0.1',port=0,threads=4)
        thread=Thread(target=server.run,daemon=True,name='SISMOC-local');thread.start()
        try:
            webview.create_window('SISMOC El Cumbe · Gestión de la empresa',
                f'http://127.0.0.1:{server.effective_port}/login/',width=1400,height=900,
                min_size=(1000,680),confirm_close=True)
            webview.start(gui='edgechromium',private_mode=False,storage_path=str(root/'webview'),debug=False,
                localization={'global.quitConfirmation':'¿Deseas cerrar SISMOC?','global.ok':'Aceptar','global.cancel':'Cancelar'})
        finally:
            detener_servidor(server,thread)


if __name__=='__main__':
    try:main()
    except Exception as error:
        logging.exception('No se pudo iniciar SISMOC')
        import ctypes
        ctypes.windll.user32.MessageBoxW(0,'No se pudo abrir SISMOC. '+str(error),'SISMOC El Cumbe',16)
