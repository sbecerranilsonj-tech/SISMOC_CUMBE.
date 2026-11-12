"""Lee las columnas del reporte original, sin ejecutar macros ni fórmulas."""
import hashlib
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from io import BytesIO
from decimal import Decimal, InvalidOperation


def abrir_xls(contenido):
    import xlrd
    try:
        return xlrd.open_workbook(file_contents=contenido, on_demand=True)
    except Exception as inicial:
        # Algunos exportadores generan directorios OLE que xlrd rechaza.
        # Recuperar el flujo no altera el archivo original ni omite filas BIFF.
        from .xls_recovery import flujo_workbook
        try:
            return xlrd.open_workbook(file_contents=flujo_workbook(contenido), on_demand=True)
        except Exception as recuperacion:
            raise ValueError(f'El lector XLS rechazó el documento ({type(inicial).__name__}: {str(inicial)[:200]}). '
                'No se pudo recuperar el libro. En Excel use Guardar como → Libro de Excel (.xlsx), sin cambiar solo la extensión, y vuelva a importarlo.') from recuperacion


def normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode().upper()
    return ' '.join(re.findall(r'[A-Z0-9]+', texto))


def identidad(texto):
    return ' '.join(sorted(normalizar(texto).split()))


def fecha_excel(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=valor)).date()
    for formato in ('%Y/%m/%d', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(str(valor).strip(), formato).date()
        except ValueError:
            pass
    raise ValueError('Fecha no reconocida')


def hora_excel(valor):
    if isinstance(valor, datetime):
        return valor.time().replace(microsecond=0)
    if isinstance(valor, time):
        return valor.replace(microsecond=0)
    if isinstance(valor, (int, float)) and 0 <= valor < 1:
        segundos = round(valor * 86400) % 86400
        return time(segundos // 3600, segundos // 60 % 60, segundos % 60)
    texto = str(valor).strip().lower().replace('.', '').replace(' ', '')
    for formato in ('%I:%M%p', '%I:%M:%S%p', '%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(texto, formato).time()
        except ValueError:
            pass
    raise ValueError('Hora no reconocida')


def interpretar_filas(filas):
    encabezado = None
    resultado, incidencias = [], []
    for numero, valores in enumerate(filas, 1):
        valores = list(valores)
        etiquetas = [normalizar(v) for v in valores]
        if 'FECHA' in etiquetas and 'ORIGEN' in etiquetas and 'DESTINO' in etiquetas:
            encabezado = {v: i for i, v in enumerate(etiquetas) if v}
            continue
        if encabezado is None:
            continue
        def campo(*claves):
            for k in claves:
                if k in encabezado:
                    i = encabezado[k]
                    return valores[i] if i < len(valores) and valores[i] is not None else ''
            return ''
        raw_fecha = campo('FECHA')
        if not raw_fecha and not campo('HORA'):
            continue
        # Los subtotales no tienen fecha y hora; una fila de salida inválida sí se reporta.
        if not campo('HORA'):
            if str(raw_fecha).strip().startswith(('20', '202')) or isinstance(raw_fecha, (date, datetime, int, float)):
                incidencias.append(f'Fila {numero}: falta la hora de salida.')
            continue
        try:
            fecha, hora = fecha_excel(raw_fecha), hora_excel(campo('HORA'))
            bus, origen, destino = (str(campo(c)).strip() for c in ('BUS', 'ORIGEN', 'DESTINO'))
            if not all((bus, origen, destino)):
                raise ValueError('Falta bus, origen o destino')
            n1 = str(campo('CONDUCTOR N 1', 'CONDUCTOR NO1', 'CONDUCTOR N1', 'CONDUCTOR 1')).strip()
            n2 = str(campo('CONDUCTOR N 2', 'CONDUCTOR NO2', 'CONDUCTOR N2', 'CONDUCTOR 2')).strip()
            anulado = any(normalizar(v) == 'ANULADO' for v in valores)
            clave = hashlib.sha256('|'.join((fecha.isoformat(), hora.isoformat(), normalizar(bus), normalizar(origen), normalizar(destino))).encode()).hexdigest()
            comercial = {}
            for nombre, columna in [('capacidad', 'CAPACIDAD'), ('vendidos_segundo_piso', 'VEND 2DO PISO'), ('vendidos_primer_piso', 'VEND 1ER PISO')]:
                valor = campo(columna)
                if valor != '':
                    try:
                        numero_decimal = Decimal(str(valor))
                        if not numero_decimal.is_finite() or numero_decimal < 0 or numero_decimal != numero_decimal.to_integral_value():
                            raise ValueError()
                        comercial[nombre] = int(numero_decimal)
                    except (InvalidOperation, ValueError):
                        incidencias.append(f'Fila {numero}: revise la cantidad de {columna.lower()}.')
            resultado.append(dict(fila=numero, fecha=fecha, hora=hora, bus=bus, origen=origen, destino=destino,
                nombre_uno=n1, nombre_dos=n2, anulado=anulado, clave=clave,
                correlativo=str(campo('CORRELATIVO')).strip(), original={**{str(i+1): str(v) if v is not None else '' for i, v in enumerate(valores)}, 'comercial': comercial}))
        except (ValueError, TypeError) as error:
            incidencias.append(f'Fila {numero}: {error}.')
    if encabezado is None:
        raise ValueError('No se encontró el encabezado del reporte de itinerarios.')
    if not resultado:
        raise ValueError('No se encontraron salidas legibles. Revise las fechas y las horas del reporte.')
    return resultado, incidencias


def extraer(archivo):
    if archivo.size > 20 * 1024 * 1024:
        raise ValueError('El archivo no debe superar 20 MB.')
    contenido = archivo.read()
    if archivo.name.lower().endswith('.xls'):
        libro = abrir_xls(contenido)
        try:
            if libro.datemode != 0:
                raise ValueError('Este reporte usa un calendario Excel diferente. Guárdelo como XLSX para importarlo.')
            hojas = [libro.sheet_by_index(i) for i in range(libro.nsheets)]
            hoja = next((h for h in hojas if h.name.lower() == 'reporte'), hojas[0])
            return interpretar_filas(hoja.row_values(i) for i in range(hoja.nrows))
        finally:
            libro.release_resources()
    if archivo.name.lower().endswith(('.xlsx', '.xlsm')):
        from openpyxl import load_workbook
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True, keep_links=False)
        try:
            if libro.epoch.year != 1899:
                raise ValueError('Calendario Excel no compatible; use fechas de texto AAAA/MM/DD.')
            hoja = next((h for h in libro if h.title.lower() == 'reporte'), libro.worksheets[0])
            return interpretar_filas(hoja.iter_rows(values_only=True))
        finally:
            libro.close()
    raise ValueError('Seleccione un reporte XLS, XLSX o XLSM.')
