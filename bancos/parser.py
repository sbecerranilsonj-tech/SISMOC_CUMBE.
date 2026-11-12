"""Extracción BCP por coordenadas: el nombre del movimiento no define su signo."""
import re
from io import BytesIO
from datetime import datetime, date
from decimal import Decimal

MESES = {m: i + 1 for i, m in enumerate('ENE FEB MAR ABR MAY JUN JUL AGO SEP OCT NOV DIC'.split())}
IMPORTE = re.compile(r'^-?\d[\d,]*\.\d{2}$')
FECHA = re.compile(r'^(\d{2})([A-Z]{3})$')


def importe(texto):
    return Decimal(texto.replace(',', ''))


def abrir_pdf(archivo):
    import pdfplumber
    archivo.seek(0)
    contenido = archivo.read()
    archivo.seek(0)
    try:
        return pdfplumber.open(BytesIO(contenido))
    except Exception as original:
        # PDFium reconstruye catálogos/trailers que PDFMiner no logra interpretar.
        # Se usa una copia en memoria; el archivo original nunca se reemplaza.
        import pypdfium2
        copia = BytesIO()
        try:
            documento = pypdfium2.PdfDocument(contenido)
            try:
                documento.save(copia)
            finally:
                documento.close()
            copia.seek(0)
            return pdfplumber.open(copia)
        except Exception as recuperacion:
            raise ValueError('El PDF tiene una estructura interna inválida o está protegido y no pudo recuperarse. Descargue de nuevo el estado original del BCP. Si se abre en su visor, guarde una copia como PDF y vuelva a cargarla.') from recuperacion


def palabras_desde_texto(pagina):
    """Segunda lectura: conserva columnas aunque el PDF fragmente las palabras."""
    texto = pagina.extract_text(layout=True, x_tolerance=2, y_tolerance=4) or ''
    palabras = []
    for y, linea in enumerate(texto.splitlines()):
        # Normaliza fechas que el emisor haya partido en día y mes.
        linea = re.sub(r'\b(\d{2})\s+([A-Z]{3})\b', lambda m: (m[1] + m[2]).ljust(len(m[0])), linea)
        for token in re.finditer(r'\S+', linea):
            palabras.append({'text': token.group(), 'x0': token.start(), 'top': y * 10})
    return palabras


def extraer(archivo, modo='palabras'):
    movimientos, incidencias, saldos = [], [], {}
    totales_banco = None
    with abrir_pdf(archivo) as pdf:
        if len(pdf.pages) > 500:
            raise ValueError('El PDF supera el límite de 500 páginas.')
        texto = pdf.pages[0].extract_text() or ''
        cuenta = re.search(r'\b\d{3}-\d{8}-\d-\d{2}\b', texto)
        periodo = re.search(r'DEL\s+(\d{2}/\d{2}/\d{2,4})\s+AL\s+(\d{2}/\d{2}/\d{2,4})', texto)
        if not cuenta or not periodo or 'SOLES' not in texto.upper():
            raise ValueError('Se requiere un estado BCP en soles con cuenta y período legibles. Los PDF escaneados necesitan OCR y no están admitidos todavía.')
        def fecha_periodo(s):
            return datetime.strptime(s, '%d/%m/%Y' if len(s) == 10 else '%d/%m/%y').date()
        inicio, fin = map(fecha_periodo, periodo.groups())
        if inicio > fin:
            raise ValueError('El período del documento es inválido.')
        def convertir(s):
            dia, mes = FECHA.fullmatch(s).groups()
            candidatos = [date(y, MESES[mes], int(dia)) for y in {inicio.year, fin.year}]
            return min(candidatos, key=lambda d: abs((d - inicio).days))
        for numero, pagina in enumerate(pdf.pages, 1):
            if numero == len(pdf.pages):
                cierre = pagina.extract_text() or ''
                total_texto = re.search(r'TOTAL\s+MOVIMIENTO\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', cierre)
                if total_texto:
                    totales_banco = tuple(importe(v) for v in total_texto.groups())
            palabras = palabras_desde_texto(pagina) if modo == 'texto' else pagina.extract_words(x_tolerance=2, y_tolerance=4)
            filas = []
            for palabra in sorted(palabras, key=lambda w: (w['top'], w['x0'])):
                if not filas or abs(palabra['top'] - filas[-1][0]['top']) > 3:
                    filas.append([])
                filas[-1].append(palabra)
            limite = None
            esperando_saldo = False
            for fila in filas:
                fila.sort(key=lambda w: w['x0'])
                cargos = next((w for w in fila if w['text'].upper().startswith('CARGOS')), None)
                abonos = next((w for w in fila if w['text'].upper().startswith('ABONOS')), None)
                if cargos and abonos:
                    limite = (cargos['x0'] + abonos['x0']) / 2
                linea = ' '.join(w['text'] for w in fila)
                numeros = [w for w in fila if IMPORTE.fullmatch(w['text'])]
                if 'TOTAL MOVIMIENTO' in linea and len(numeros) == 2:
                    totales_banco = tuple(importe(w['text']) for w in numeros)
                if esperando_saldo and numeros:
                    saldos['final'] = importe(numeros[-1]['text'])
                    esperando_saldo = False
                if 'SALDOANTERIOR' in linea.replace(' ', '') and numeros:
                    saldos['inicial'] = importe(numeros[-1]['text'])
                elif any(w['text'].upper() == 'SALDO' for w in fila) and 'ANTERIOR' not in linea:
                    if numeros:
                        saldos['final'] = importe(numeros[-1]['text'])
                    else:
                        esperando_saldo = True
                if not fila or not FECHA.fullmatch(fila[0]['text']):
                    continue
                if len(fila) < 4 or not FECHA.fullmatch(fila[1]['text']) or len(numeros) != 1 or limite is None:
                    incidencias.append(f'Página {numero}: {linea}')
                    continue
                try:
                    fecha, valor = convertir(fila[0]['text']), convertir(fila[1]['text'])
                    monto = importe(numeros[0]['text'])
                    if monto <= 0 or not inicio <= fecha <= fin:
                        raise ValueError('Importe o fecha fuera del período')
                    descripcion = ' '.join(w['text'] for w in fila[2:] if w is not numeros[0]).strip()
                    movimientos.append(dict(orden=len(movimientos) + 1, pagina=numero, fecha=fecha, fecha_valor=valor, descripcion=descripcion, cargo=monto if numeros[0]['x0'] < limite else Decimal('0'), abono=monto if numeros[0]['x0'] >= limite else Decimal('0'), original={'linea': linea, 'pagina': numero}))
                except (ValueError, KeyError):
                    incidencias.append(f'Página {numero}: {linea}')
            # En este formato BCP, SALDO puede compartir altura con el pie legal.
            # Busca el importe impreso de cierre, nunca lo deduce de los movimientos.
            if numero == len(pdf.pages) and limite is not None:
                fechas_y = [w['top'] for w in palabras if FECHA.fullmatch(w['text'])]
                ultima_fila = max(fechas_y, default=-1)
                candidatos = []
                candidatos_totales = []
                for fila in filas:
                    linea = ' '.join(w['text'] for w in fila).upper()
                    numeros_fila = [w for w in fila if IMPORTE.fullmatch(w['text'])]
                    if len(numeros_fila) == 2 and all(w['top'] > ultima_fila + 3 for w in numeros_fila) and numeros_fila[0]['x0'] < limite <= numeros_fila[1]['x0']:
                        candidatos_totales.append(tuple(importe(w['text']) for w in numeros_fila))
                    if 'TOTAL' in linea and 'MOVIMIENTO' in linea:
                        continue
                    numeros = [w for w in fila if IMPORTE.fullmatch(w['text'])]
                    if len(numeros) == 1 and numeros[0]['x0'] >= limite and numeros[0]['top'] > ultima_fila + 3:
                        candidatos.append(importe(numeros[0]['text']))
                if 'final' not in saldos and len(candidatos) == 1:
                    saldos['final'] = candidatos[0]
                if totales_banco is None and len(candidatos_totales) == 1:
                    totales_banco = candidatos_totales[0]
    if not movimientos or 'inicial' not in saldos or 'final' not in saldos:
        if modo == 'palabras':
            return extraer(archivo, modo='texto')
        faltantes = []
        if not movimientos:
            faltantes.append('movimientos reconocibles')
        if 'inicial' not in saldos:
            faltantes.append('saldo inicial')
        if 'final' not in saldos:
            faltantes.append('saldo final')
        raise ValueError(f'No se pudo completar la lectura del PDF: falta {", ".join(faltantes)}. Se reconocieron {len(movimientos)} movimientos y {len(incidencias)} líneas con problemas. No se guardó la importación.')
    calculados = tuple(sum((m[campo] for m in movimientos), Decimal('0')) for campo in ('cargo', 'abono'))
    if totales_banco is None:
        incidencias.append('No se pudieron verificar los totales de cargos y abonos del documento.')
    elif calculados != totales_banco:
        incidencias.append(f'Totales que no coinciden: cargos leídos S/ {calculados[0]:,.2f} frente a S/ {totales_banco[0]:,.2f} del PDF; abonos leídos S/ {calculados[1]:,.2f} frente a S/ {totales_banco[1]:,.2f} del PDF.')
    return dict(cuenta=cuenta.group(), inicio=inicio, fin=fin, saldo_inicial=saldos['inicial'], saldo_final=saldos['final'], incidencias=incidencias), movimientos
