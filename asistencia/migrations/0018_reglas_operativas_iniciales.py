from datetime import date, timedelta
import unicodedata
from django.db import migrations


def normalizar(valor):
    return ''.join(c for c in unicodedata.normalize('NFD', valor or '') if not unicodedata.combining(c)).strip().casefold()


def cargar(apps, schema_editor):
    alias = schema_editor.connection.alias
    Regla = apps.get_model('asistencia', 'ReglaJornada')
    Trabajador = apps.get_model('asistencia', 'Trabajador')
    Cierre = apps.get_model('asistencia', 'CierreAsistencia')
    desde = date(2026, 10, 30)
    ultimo = Cierre.objects.using(alias).order_by('-fecha_fin').first()
    if ultimo and ultimo.fecha_fin >= desde:
        desde = ultimo.fecha_fin + timedelta(days=1)
    motivo = 'Regla inicial según indicación operativa del 30/10/2026.'
    Regla.objects.using(alias).create(desde=desde, minutos_diarios=480, minutos_sabado=240, minutos_refrigerio=45, motivo=motivo)
    areas = set(Trabajador.objects.using(alias).values_list('area', flat=True)) | {'Contabilidad', 'Administración', 'Mecánica'}
    creadas = set()
    for area in sorted(areas):
        clave = normalizar(area)
        if clave in creadas:
            continue
        contable = 'contab' in clave
        if contable or 'administra' in clave or 'mecanic' in clave:
            Regla.objects.using(alias).create(area=area, desde=desde, minutos_diarios=510 if contable else 480,
                                             minutos_sabado=270 if contable else 240, minutos_refrigerio=60, motivo=motivo)
            creadas.add(clave)
    # Solo identidad por nombre completo exacto, independientemente del orden.
    nombres = [{'blanca', 'gladis', 'pelaez', 'castrejon'}, {'deidamia', 'garcia', 'castro'}]
    fichas = list(Trabajador.objects.using(alias).all())
    for nombre in nombres:
        coincidencias = [t for t in fichas if set(normalizar(t.nombre_completo).split()) == nombre]
        if len(coincidencias) == 1:
            Regla.objects.using(alias).create(trabajador_id=coincidencias[0].pk, desde=desde,
                                             minutos_diarios=480, minutos_sabado=240, minutos_refrigerio=45,
                                             exento_marcacion=True, motivo=motivo + ' Socia exonerada de marcación.')


class Migration(migrations.Migration):
    dependencies = [('asistencia', '0017_diaespecial_reglajornada')]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
