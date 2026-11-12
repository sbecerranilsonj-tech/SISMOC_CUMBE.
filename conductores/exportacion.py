"""Libro de control con calendario y resumen del período consultado."""
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins


def libro_calendario(inicio, fin, dias, filas, filas_resumen=None):
    filas_resumen = filas if filas_resumen is None else filas_resumen
    wb = Workbook()
    calendario = wb.active
    calendario.title = 'Calendario'
    resumen = wb.create_sheet('Resumen del período')
    campos = ('trayectos', 'trabajados', 'descansos', 'vueltas', 'pago_vueltas', 'horas', 'una_x', 'dos_x', 'pendientes')
    cabeceras = ['Conductor', 'Trayectos', 'Días con viajes', 'Descansos', 'Vueltas', 'Pago por vueltas', 'HORA', 'X', 'XX', 'Pendientes']
    for ws, headers in [(calendario, ['Conductor'] + [d.strftime('%d/%m') for d in dias]), (resumen, cabeceras)]:
        n = len(headers)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
        ws.cell(1, 1, 'EL CUMBE · CONTROL DE CONDUCTORES')
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n)
        ws.cell(2, 1, f'Período: {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}')
        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=n)
        ws.cell(3, 1, 'HORA: 1 trayecto · X: 2 · XX: 3 · D: descanso · V: vacaciones · DS: descuento · LC/LS: licencia · SV: sin ventas, sin pago · C: cancelado, sin pago · —: pendiente' if ws == calendario else 'Pago por vueltas = vueltas × S/ 20.00. Los conteos corresponden al período y conductor consultados.')
        ws.append(headers)
        ws.freeze_panes = 'B5'
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = 'landscape'
        ws.page_setup.paperSize = ws.PAPERSIZE_A3 if ws == calendario else ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = '1:4'
        ws.page_margins = PageMargins(left=.25, right=.25, top=.4, bottom=.4, header=.15, footer=.15)
        ws.oddFooter.center.text = 'Página &P de &N'
        ws.row_dimensions[1].height = 32
        ws.row_dimensions[2].height = 24
        ws.row_dimensions[3].height = 32
        ws.row_dimensions[4].height = 36
        ws.column_dimensions['A'].width = 43
        for col in range(2, n+1):
            ws.column_dimensions[get_column_letter(col)].width = 9 if ws == calendario else (20 if col == 6 else 16)
    for f in filas:
        calendario.append([f['conductor'].nombre_apellidos] + [c['etiqueta'] for c in f['celdas']])
    for f in filas_resumen:
        resumen.append([f['conductor'].nombre_apellidos] + [f[k] for k in campos])
    total_row = resumen.max_row + 1
    resumen.cell(total_row, 1, 'TOTAL')
    for col, campo in enumerate(campos, 2):
        resumen.cell(total_row, col, sum(f[campo] for f in filas_resumen))
    for ws in wb:
        for row in ws:
            for cell in row:
                cell.font = Font(name='Calibri', size=11, color='243447')
                cell.alignment = Alignment(vertical='center', horizontal='left' if cell.column == 1 else 'center', wrap_text=True)
                if cell.row == 1 or cell.row == 4 or (ws == resumen and cell.row == total_row):
                    cell.fill = PatternFill('solid', fgColor='192632')
                    cell.font = Font(name='Calibri', size=15 if cell.row == 1 else 11, bold=True, color='FFFFFF')
                elif cell.row >= 5:
                    cell.fill = PatternFill('solid', fgColor='F2F5F8' if cell.row % 2 else 'FFFFFF')
                    cell.border = Border(bottom=Side(style='hair', color='DCE3EB'))
                    if ws == calendario and cell.column > 1:
                        value = str(cell.value)
                        color = 'FFF0DD' if value in ('X','XX') or ':' in value else 'E2F1EA' if value == 'D' else 'E8E5F5' if value in ('V','LC','LS','P','L','DS') else 'FFF2CC' if value == 'SV' else 'F9E6E6' if value == 'C' else 'F2F5F8'
                        cell.fill = PatternFill('solid', fgColor=color)
                        cell.font = Font(name='Calibri', size=11, bold=True, color='A64E0C' if color == 'FFF0DD' else '243447')
                    if cell.data_type == 'f':
                        cell.data_type = 's'
        for r in range(5, ws.max_row+1):
            ws.row_dimensions[r].height = 32
        ws.auto_filter.ref = f'A4:{get_column_letter(ws.max_column)}{max(4,ws.max_row-(1 if ws==resumen else 0))}'
        ws.print_options.horizontalCentered = True
        ws.print_area = f'A1:{get_column_letter(ws.max_column)}{ws.max_row}'
    for row in resumen.iter_rows(min_row=5):
        row[4].number_format = '0.0'
        row[5].number_format = '"S/ "#,##0.00'
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
