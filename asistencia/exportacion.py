"""Libro de asistencia: resumen filtrado, detalle diario y ficha por trabajador."""
import re
from datetime import date
from io import BytesIO
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.workbook.properties import CalcProperties
from django.utils import timezone
from asistencia.services.revision import valores_ajustados, estado_revision

METRICAS = ('horas_trabajadas', 'horas_extras_25', 'horas_extras_35', 'horas_nocturnas', 'descanso_feriado')
RESUMEN_HEADERS = ['Código importado', 'Trabajador', 'Área', 'Sede', 'Jornadas', 'Horas efectivas',
                   'Extras 25 %', 'Extras 35 %', 'Nocturnas', 'Descanso / feriado', 'Tiempo faltante',
                   'Aprobadas', 'Pendientes']
RESUMEN_WIDTHS = [20, 43, 25, 20, 12, 15, 14, 14, 14, 17, 17, 13, 13]
DETALLE_HEADERS = ['Fecha', 'Código importado', 'Trabajador', 'Sede', 'Horas efectivas',
                   'Extras 25 %', 'Extras 35 %', 'Nocturnas', 'Descanso / feriado', 'Revisión']
DETALLE_WIDTHS = [15, 22, 43, 22, 17, 15, 15, 15, 19, 18]
VERDE = '173C35'
TINTA = '20343B'
TEAL = '087F78'
BORDE = 'DCE6E5'


def codigo_importado(persona):
    valor = getattr(persona, 'codigo', '') or getattr(persona, 'zkteco_user_id', '') or ''
    if not valor and persona._meta.label_lower == 'core.usuario':
        from asistencia.models import IdentidadBiometrica
        from django.db.models import Q
        valor = ' / '.join(sorted(set(IdentidadBiometrica.objects.filter(Q(usuario_id=persona.pk) | Q(trabajador__usuario_id=persona.pk)).values_list('codigo', flat=True))))
    return ' / '.join(c.strip() for c in str(valor).split(' / ') if c.strip() and not c.strip().upper().startswith('CUM-')) or 'Sin código importado'


def nombre_corto(persona):
    """Nombre y primer apellido: mantiene las pestañas del Excel legibles."""
    nombres = str(getattr(persona, 'nombres', '') or getattr(persona, 'first_name', '') or '').split()
    apellidos = str(getattr(persona, 'apellido_paterno', '') or getattr(persona, 'last_name', '') or '').split()
    if nombres and apellidos:
        return f'{nombres[0]} {apellidos[0]}'
    partes = str(getattr(persona, 'nombre_completo', '') or '').split()
    return ' '.join(partes[:2]) if partes else 'Sin nombre'


def texto(ws, fila, columna, valor):
    cell = ws.cell(fila, columna, str(valor))
    cell.data_type = 's'
    return cell


def banda(ws, row, start, end, label, color=VERDE, foreground='FFFFFF', size=11):
    ws.merge_cells(start_row=row, start_column=start, end_row=row, end_column=end)
    for col in range(start, end + 1):
        cell = ws.cell(row, col)
        cell.fill = PatternFill('solid', fgColor=color)
        cell.alignment = Alignment(horizontal='left', vertical='center', indent=1)
    cell = texto(ws, row, start, label)
    cell.font = Font(name='Calibri', size=size, bold=True, color=foreground)


def preparar(ws, titulo, filtros, headers, widths):
    n = len(headers)
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 85
    ws.sheet_properties.tabColor = TEAL
    banda(ws, 1, 1, n, 'EL CUMBE  |  CONTROL DE ASISTENCIA', size=17)
    banda(ws, 2, 1, n, titulo, color='E9F2EF', foreground=VERDE, size=12)
    inicio, fin = date.fromisoformat(filtros['desde']), date.fromisoformat(filtros['hasta'])
    banda(ws, 3, 1, n, f'Periodo: {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}', color='FFFFFF', foreground=TINTA)
    claves = [('sede', 'Sede'), ('area', 'Área'), ('trabajador', 'Trabajador'), ('revision', 'Revisión'), ('estado', 'Situación')]
    seleccion = ' · '.join(f'{label}: {filtros[key]}' for key, label in claves if filtros.get(key))
    banda(ws, 4, 1, n, seleccion or 'Todas las sedes y áreas · Consulta completa del periodo', color='FFFFFF', foreground='52676C', size=10)
    for col, label in enumerate(headers, 1):
        cell = texto(ws, 9, col, label)
        cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor=VERDE)
        cell.alignment = Alignment(wrap_text=True, horizontal='left' if col < 5 else 'center', vertical='center', indent=1)
        ws.column_dimensions[get_column_letter(col)].width = widths[col - 1]
    for row, height in [(1, 38), (2, 26), (3, 24), (4, 26), (5, 22), (6, 28), (7, 10), (8, 23), (9, 36)]:
        ws.row_dimensions[row].height = height
    ws.freeze_panes = 'C10'
    ws.print_title_rows = '1:9'
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins = PageMargins(left=.25, right=.25, top=.35, bottom=.35, header=.15, footer=.15)
    ws.oddFooter.left.text = 'SISMOC · Asistencia'
    ws.oddFooter.right.text = 'Página &P de &N'


def cuerpo(ws, fila, values, formatos):
    for col, value in enumerate(values, 1):
        cell = texto(ws, fila, col, value) if isinstance(value, str) else ws.cell(fila, col, value)
        cell.font = Font(name='Calibri', size=11, color=TINTA)
        cell.fill = PatternFill('solid', fgColor='FFFFFF' if fila % 2 == 0 else 'F3F7F6')
        cell.border = Border(bottom=Side(style='hair', color=BORDE))
        cell.alignment = Alignment(vertical='center', horizontal='left' if col <= 4 else 'center', wrap_text=True)
        if col in formatos:
            cell.number_format = formatos[col]
    ws.row_dimensions[fila].height = 32


def nombre_hoja(base, usados):
    limpio = re.sub(r'[\\/*?:\[\]]', ' ', str(base or 'Sin nombre')).strip()[:31] or 'Hoja'
    candidato = limpio
    indice = 2
    while candidato in usados:
        sufijo = f' ({indice})'
        candidato = limpio[:31 - len(sufijo)] + sufijo
        indice += 1
    usados.add(candidato)
    return candidato


def hoja_resumen(ws, filtros, filas, titulo):
    preparar(ws, titulo, filtros, RESUMEN_HEADERS, RESUMEN_WIDTHS)
    filas = sorted(filas, key=lambda f: (f['usuario'].agencia_sede or '',
                                        nombre_corto(f['usuario']).casefold()))
    for start, end, label, value in [(1, 4, 'TRABAJADORES', len(filas)),
                                     (5, 8, 'JORNADAS', sum(f['jornadas'] for f in filas)),
                                     (9, 11, 'APROBADAS', sum(f['aprobadas'] for f in filas)),
                                     (12, 13, 'POR REVISAR', sum(f['pendientes'] for f in filas))]:
        banda(ws, 5, start, end, label, color='EDF3F2', foreground='52676C', size=10)
        banda(ws, 6, start, end, str(value), color='EDF3F2', foreground=VERDE, size=18)
    banda(ws, 8, 1, 4, 'PERSONAL', color=TEAL)
    banda(ws, 8, 5, 11, 'JORNADA Y HORAS', color=TEAL)
    banda(ws, 8, 12, 13, 'REVISIÓN CONTABLE', color=TEAL)
    for row, f in enumerate(filas, 10):
        u = f['usuario']
        values = [codigo_importado(u), nombre_corto(u), getattr(u, 'area', '') or 'Sin área',
                  u.agencia_sede, f['jornadas'], *[f[k] for k in METRICAS],
                  f['faltante_segundos'] / 86400, f['aprobadas'], f['pendientes']]
        cuerpo(ws, row, values, {**{c: '0.00' for c in range(6, 11)}, 11: '[h]:mm:ss'})
        if ws.cell(row, 12).value:
            ws.cell(row, 12).fill = PatternFill('solid', fgColor='E6F3EC')
            ws.cell(row, 12).font = Font(name='Calibri', size=11, bold=True, color='16634D')
        if f.get('faltante_por_revisar'):
            ws.cell(row, 11).comment = Comment(
                f"{f['faltante_por_revisar']} jornadas requieren revisión. El tiempo faltante solo incluye jornadas calculables.", 'SISMOC')
    last = 9 + len(filas)
    ws.auto_filter.ref = f'A9:M{max(9, last)}'
    if not filas:
        banda(ws, 10, 1, 13, 'No hay jornadas para los filtros seleccionados.', color='F3F7F6', foreground='52676C')
    total = max(11, last + 1)
    banda(ws, total, 1, 4, 'TOTAL DEL PERIODO')
    for col in range(5, 14):
        cell = ws.cell(total, col, f'=SUM({get_column_letter(col)}10:{get_column_letter(col)}{last})' if filas else 0)
        cell.fill = PatternFill('solid', fgColor=VERDE)
        cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.number_format = '[h]:mm:ss' if col == 11 else ('0.00' if 6 <= col <= 10 else '0')
    ws.row_dimensions[total].height = 28
    banda(ws, total + 2, 1, 13, 'Horas en decimales · Tiempo faltante en horas:minutos:segundos · Detalle y fichas por trabajador en las siguientes hojas.',
          color='FFFFFF', foreground='52676C', size=10)
    ws.print_area = f'A1:M{total + 2}'
    return ws


def hoja_detalle(ws, filtros, resumenes, titulo, etiqueta=None):
    preparar(ws, titulo, filtros, DETALLE_HEADERS, DETALLE_WIDTHS)
    banda(ws, 5, 1, 10, etiqueta or f'{len(resumenes)} jornadas incluidas en la consulta',
          color='EDF3F2', foreground=VERDE)
    banda(ws, 8, 1, 4, 'IDENTIFICACIÓN', color=TEAL)
    banda(ws, 8, 5, 10, 'HORAS Y REVISIÓN', color=TEAL)
    for row, resumen in enumerate(sorted(resumenes, key=lambda r: (r.fecha, r.pk)), 10):
        valores = valores_ajustados(resumen)
        cuerpo(ws, row, [resumen.fecha, codigo_importado(resumen.persona),
                         nombre_corto(resumen.persona), resumen.persona.agencia_sede,
                         *[valores[k] for k in METRICAS], estado_revision(resumen).capitalize()],
               {1: 'dd/mm/yyyy', **{c: '0.00' for c in range(5, 10)}})
    if not resumenes:
        banda(ws, 10, 1, 10, 'No hay jornadas para los filtros seleccionados.', color='F3F7F6', foreground='52676C')
    ws.auto_filter.ref = f'A9:J{max(9, 9 + len(resumenes))}'
    ws.freeze_panes = 'D10'
    ws.print_area = f'A1:J{max(10, 9 + len(resumenes))}'
    return ws



FICHA_HEADERS = ['Código / DNI', 'Fecha/Hora', 'Evento', 'Duración del intervalo',
                 'Refrigerio', 'Jornada base', 'Saldo de jornada',
                 'HH.EE. 25 %\nPrimeras 2 h', 'HH.EE. 35 %\nExceso de 2 h',
                 'Horas nocturnas\n22:00–06:00', 'Feriado y/o descanso', 'Acciones']


def hoja_ficha(ws, filtros, persona, jornadas, titulo, detalles=None):
    """Ficha por trabajador con el control diario ya registrado en el sistema."""
    n = len(FICHA_HEADERS)
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 85
    ws.sheet_properties.tabColor = '173C35'
    banda(ws, 1, 1, n, 'EL CUMBE  |  CONTROL DE ASISTENCIA', size=17)
    banda(ws, 2, 1, n, titulo, color='E9F2EF', foreground=VERDE, size=12)
    inicio, fin = date.fromisoformat(filtros['desde']), date.fromisoformat(filtros['hasta'])
    banda(ws, 3, 1, n, f'Periodo: {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}', color='FFFFFF', foreground=TINTA)
    banda(ws, 4, 1, n, 'Control diario del sistema · intervalos y conceptos registrados · espacios para datos pendientes',
          color='FFFFFF', foreground='52676C', size=10)
    banda(ws, 5, 1, n, f'{len(jornadas)} jornadas · {getattr(persona, "agencia_sede", "") or "Sin sede"}',
          color='EDF3F2', foreground=VERDE, size=12)
    anchos = [20, 23, 32, 22, 16, 16, 18, 20, 20, 22, 24, 28]
    for col, (label, ancho) in enumerate(zip(FICHA_HEADERS, anchos), 1):
        cell = texto(ws, 8, col, label)
        cell.font = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor=VERDE)
        cell.alignment = Alignment(wrap_text=True, horizontal='center', vertical='center')
        ws.column_dimensions[get_column_letter(col)].width = ancho
    ws.row_dimensions[8].height = 38
    ws.freeze_panes = 'C9'
    ws.print_title_rows = '1:8'

    if detalles is None:
        from asistencia.services.revision_trabajador import detalles_en_lote
        detalles = {d['resumen'].pk: d for d in detalles_en_lote(jornadas)}

    def escribir(valores, color=None, negrita=False):
        nonlocal fila
        for col, valor in enumerate(valores, 1):
            cell = texto(ws, fila, col, valor) if isinstance(valor, str) else ws.cell(fila, col, valor)
            cell.font = Font(name='Calibri', size=11, color=TINTA, bold=negrita)
            cell.alignment = Alignment(vertical='center',
                                       horizontal='left' if col <= 3 or col == 11 else 'center',
                                       wrap_text=True)
            cell.border = Border(bottom=Side(style='hair', color=BORDE))
            if col == 2:
                cell.number_format = 'dd/mm/yyyy hh:mm:ss'
            if color:
                cell.fill = PatternFill('solid', fgColor=color)
        ws.row_dimensions[fila].height = 32
        fila += 1

    def tiempo(valor):
        return '' if valor in (None, 'Por revisar', 'Sin registro', '—') else valor

    fila = 9
    for resumen in sorted(jornadas, key=lambda r: (r.fecha, r.pk)):
        detalle = detalles[resumen.pk]
        cuadro = detalle['cuadro_excel']
        situacion = detalle.get('situacion_dia')
        estado = situacion.get_tipo_display() if situacion else resumen.get_estado_display()
        etiqueta = str(estado or '')
        especial = str(getattr(resumen, '_calendario_feriados', {}).get(resumen.fecha, '') or '')
        descripcion = f'{etiqueta} {especial}'.upper()
        color = ('DBEAFE' if 'PERMISO' in descripcion else
                 'EDE3F8' if 'DESCANSO' in descripcion or detalle.get('descanso_previsto') else
                 'FFF2CC' if 'FERIADO' in descripcion else
                 'E2F0D9' if 'VACACION' in descripcion else 'EDF3F2')
        for marca in cuadro['filas']:
            accion = ('Excluida por duplicada · No computa' if marca.get('excluida_duplicada') else
                      'Invalidada · No computa' if not marca['valida'] else
                      'Manual' if marca['es_manual'] else '')
            momento = marca['fecha_hora'].replace(tzinfo=None)
            escribir([marca['codigo'], momento, str(marca['evento']), tiempo(marca['intervalo']),
                      'REFRIGERIO' if marca['es_refrigerio'] else '',
                      '', '', '', '', '', '', accion],
                     'FFF2CC' if marca['es_refrigerio'] else None)
        if not cuadro['filas']:
            escribir([codigo_importado(persona), resumen.fecha, etiqueta,
                      '', '', '', '', '', '', '', '', ''], color)
        totales = cuadro['totales']
        escribir(['', resumen.fecha, 'Total trabajado y conceptos del día',
                  tiempo(totales['trabajo']), tiempo(cuadro['refrigerio']),
                  tiempo(totales['base']), tiempo(totales['saldo']),
                  tiempo(totales['he25']), tiempo(totales['he35']),
                  tiempo(totales['nocturnas']), tiempo(totales['feriado']),
                  detalle['revision']], color, True)
    if not jornadas:
        banda(ws, 9, 1, n, 'No hay jornadas registradas para este trabajador en el periodo.',
              color='F3F7F6', foreground='52676C')
    ws.print_area = f'A1:{get_column_letter(n)}{max(9, fila - 1)}'
    return ws


def libro_asistencia(filtros, filas, resumenes, detalles=None):
    wb = Workbook()
    wb.properties.creator = 'SISMOC · El Cumbe'
    wb.properties.title = 'Control de asistencia'
    wb.calculation = CalcProperties(calcId=191029, fullCalcOnLoad=True)
    usados = set()
    if detalles is None:
        from asistencia.services.revision_trabajador import detalles_en_lote
        detalles = detalles_en_lote(resumenes)
    detalles = {d['resumen'].pk: d for d in detalles}

    resumen = wb.active
    resumen.title = nombre_hoja('Resumen de asistencia', usados)
    hoja_resumen(resumen, filtros, filas, 'RESUMEN POR TRABAJADOR')

    por_dni = {}
    for resumen_diario in resumenes:
        por_dni.setdefault(getattr(resumen_diario.persona, 'dni', ''), []).append(resumen_diario)

    sedes = {}
    for fila in filas:
        sedes.setdefault(fila['usuario'].agencia_sede or 'Sin sede', []).append(fila)

    for sede, filas_sede in sorted(sedes.items(), key=lambda par: par[0].casefold()):
        hoja_sede = wb.create_sheet(nombre_hoja(sede, usados))
        hoja_sede.sheet_properties.tabColor = 'F26522'
        hoja_resumen(hoja_sede, filtros, filas_sede, f'RESUMEN POR SEDE · {sede.upper()}')
        for fila in sorted(filas_sede, key=lambda f: nombre_corto(f['usuario']).casefold()):
            usuario = fila['usuario']
            ficha = wb.create_sheet(nombre_hoja(nombre_corto(usuario), usados))
            hoja_ficha(ficha, filtros, usuario, por_dni.get(usuario.dni, []),
                       f'FICHA POR TRABAJADOR · {nombre_corto(usuario).upper()}', detalles)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()
