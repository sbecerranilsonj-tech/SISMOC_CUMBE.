import sys
from io import BytesIO
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch, MagicMock
from .parser import extraer, abrir_pdf


class ParserBCPTests(TestCase):
    def test_totales_impresos_en_altura_distinta_del_rotulo(self):
        motor = self.documento()
        pagina = motor.open(None).__enter__.return_value.pages[0]
        palabras = pagina.extract_words()
        for palabra in palabras:
            if palabra['top'] == 50 and palabra['text'] != 'TOTAL MOVIMIENTO':
                palabra['top'] = 55
        pagina.extract_words = lambda **kwargs: palabras
        with patch.dict(sys.modules, {'pdfplumber': motor}):
            datos, _ = extraer(BytesIO())
        self.assertEqual(datos['incidencias'], [])

    def test_saldo_final_comparte_fila_con_pie_legal(self):
        motor = self.documento()
        contexto = motor.open(None)
        pagina = contexto.__enter__.return_value.pages[0]
        original = pagina.extract_words()
        # El pie empieza antes que la etiqueta SALDO y comparte su línea base.
        original.extend([{'x0': -20, 'top': 60, 'text': 'la cuenta y aprobado'}, {'x0': 30, 'top': 60, 'text': 'el saldo'}])
        pagina.extract_words = lambda **kwargs: original
        with patch.dict(sys.modules, {'pdfplumber': motor}):
            estado, movimientos = extraer(BytesIO())
        self.assertEqual(estado['saldo_final'], Decimal('185.00'))
        self.assertEqual(len(movimientos), 3)

    def test_saldo_final_impreso_sin_etiqueta_reconocible(self):
        motor = self.documento()
        pagina = motor.open(None).__enter__.return_value.pages[0]
        palabras = [w for w in pagina.extract_words() if not (w['text'] == 'SALDO' and w['top'] == 60)]
        pagina.extract_words = lambda **kwargs: palabras
        with patch.dict(sys.modules, {'pdfplumber': motor}):
            estado, _ = extraer(BytesIO())
        self.assertEqual(estado['saldo_final'], Decimal('185.00'))

    def test_segunda_lectura_recupera_fechas_fragmentadas(self):
        texto = '\n'.join([
            '                        CARGOS        ABONOS',
            'SALDO ANTERIOR                           100.00',
            '01 JUL 01 JUL Yape salida  5.00',
            '01 JUL 01 JUL Yape ingreso                  90.00',
            'TOTAL MOVIMIENTO          5.00             90.00',
            'SALDO',
            '                                          185.00',
        ])
        pagina = SimpleNamespace(extract_text=lambda **kwargs: texto if kwargs else '305-00459702-0-32 SOLES DEL 01/07/26 AL 31/07/26', extract_words=lambda **kwargs: [])
        contexto = MagicMock()
        contexto.__enter__.return_value = SimpleNamespace(pages=[pagina])
        with patch('bancos.parser.abrir_pdf', return_value=contexto):
            estado, movimientos = extraer(BytesIO())
        self.assertEqual(len(movimientos), 2)
        self.assertEqual(estado['saldo_final'], Decimal('185.00'))
        self.assertEqual(estado['incidencias'], [])

    def test_recupera_catalogo_sin_modificar_original(self):
        archivo = BytesIO(b'%PDF-original')
        lector = MagicMock()
        lector.open.side_effect = [RuntimeError('No /Root object!'), 'documento recuperado']
        documento = MagicMock()
        documento.save.side_effect = lambda salida: salida.write(b'%PDF-reparado')
        motor = SimpleNamespace(PdfDocument=MagicMock(return_value=documento))
        with patch.dict(sys.modules, {'pdfplumber': lector, 'pypdfium2': motor}):
            self.assertEqual(abrir_pdf(archivo), 'documento recuperado')
        self.assertEqual(archivo.getvalue(), b'%PDF-original')
        self.assertEqual(archivo.tell(), 0)
        documento.close.assert_called_once()
        self.assertEqual(lector.open.call_args.args[0].getvalue(), b'%PDF-reparado')

    def test_recuperacion_imposible_da_error_especifico(self):
        lector = SimpleNamespace(open=MagicMock(side_effect=RuntimeError('No /Root object!')))
        motor = SimpleNamespace(PdfDocument=MagicMock(side_effect=RuntimeError('archivo dañado')))
        with patch.dict(sys.modules, {'pdfplumber': lector, 'pypdfium2': motor}):
            with self.assertRaisesRegex(ValueError, 'no pudo recuperarse'):
                abrir_pdf(BytesIO(b'%PDF-invalido'))

    def documento(self, total_abono='90.00', linea_invalida=False):
        filas = [
            [(0, 'CARGOS'), (500, 'ABONOS')],
            [(0, 'SALDO'), (60, 'ANTERIOR'), (550, '100.00')],
            [(0, '01JUL'), (50, '01JUL'), (100, 'Yape salida'), (200, '5.00')],
            [(0, '01JUL'), (50, '01JUL'), (100, 'Yape repetido'), (550, '45.00')],
            [(0, '01JUL'), (50, '01JUL'), (100, 'Yape repetido'), (550, '45.00')],
            [(0, 'TOTAL MOVIMIENTO'), (200, '5.00'), (550, total_abono)],
            [(0, 'SALDO')], [(550, '185.00')],
        ]
        if linea_invalida:
            filas.insert(3, [(0, '01JUL'), (50, 'ILEGIBLE')])
        palabras = [dict(x0=x, top=y * 10, text=t) for y, fila in enumerate(filas) for x, t in fila]
        pagina = SimpleNamespace(extract_text=lambda: '305-00459702-0-32 SOLES DEL 01/07/26 AL 31/07/26', extract_words=lambda **kwargs: palabras)
        contexto = MagicMock()
        contexto.__enter__.return_value = SimpleNamespace(pages=[pagina])
        return SimpleNamespace(open=lambda archivo: contexto)

    def test_signo_por_columna_repetidos_y_saldo_en_linea_siguiente(self):
        with patch.dict(sys.modules, {'pdfplumber': self.documento()}):
            estado, movimientos = extraer(BytesIO())
        self.assertEqual(estado['saldo_final'], Decimal('185.00'))
        self.assertEqual(estado['incidencias'], [])
        self.assertEqual(len(movimientos), 3)
        self.assertEqual(movimientos[0]['cargo'], Decimal('5.00'))
        self.assertEqual(movimientos[1]['abono'], Decimal('45.00'))

    def test_totales_incorrectos_y_filas_ilegibles_se_conservan_como_incidencias(self):
        with patch.dict(sys.modules, {'pdfplumber': self.documento('95.00', True)}):
            estado, _ = extraer(BytesIO())
        self.assertEqual(len(estado['incidencias']), 2)
