# Ejecutar desde la raíz: python -m PyInstaller desktop/Sismoc.spec --noconfirm
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

root=Path(SPECPATH).parent
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings_desktop',SISMOC_EDITION='escritorio',
    SISMOC_LOAD_DOTENV='False',SISMOC_DESKTOP_SECRET='solo-analisis-de-compilacion-'+'x'*64)
apps=['core','asistencia','bancos','conductores','movil','config','desktop',
      'corsheaders','ninja','whitenoise']
hidden=sum((collect_submodules(app,filter=lambda name: not any(part.startswith('test') for part in name.split('.'))) for app in apps),[])
data=[(str(root/'templates'),'templates'),(str(root/'static'),'static')]
data+=collect_data_files('webview')
for app in apps:
    migration=root/app/'migrations'
    if migration.is_dir():data.append((str(migration),app+'/migrations'))
a=Analysis([str(root/'desktop'/'launcher.py')],pathex=[str(root)],binaries=collect_dynamic_libs('webview'),datas=data,
    hiddenimports=hidden,excludes=['PyQt5','PyQt6','PySide2','PySide6','matplotlib','scipy','pytest'],
    noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='SISMOC',debug=False,
    strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='SISMOC')
