import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pdf/pdf.dart';
import 'package:sismoc_movil/abordaje.dart';
import 'package:sismoc_movil/api.dart';

DatosAbordaje detallePrueba({bool editable = true}) => {
  'hoy': '2026-11-25', 'operario': 'OPERARIO DE PRUEBA',
  'puede_modificar': editable,
  'empresa': {'nombre': 'EMPRESA DE PRUEBA', 'ruc': '', 'direccion': ''},
  'viaje': {'id': 1, 'fecha': '2026-11-25', 'hora': '13:50', 'bus': 'BUS PRUEBA',
    'origen': 'Origen registrado', 'destino': 'Destino registrado', 'capacidad': 60,
    'estado': 'PROGRAMADO', 'conductores': [
      {'nombre': 'CONDUCTOR DE PRUEBA', 'dni': ''},
    ], 'responsables': ['OPERARIO DE PRUEBA']},
  'pasajeros': [
    {'id': 4, 'referencia': 'BOLETO-01', 'nombre': 'PASAJERO DE PRUEBA',
      'documento': '00000001', 'piso': 1, 'asiento': 1,
      'origen': 'Origen registrado', 'destino': 'Destino registrado',
      'punto': 'Paradero intermedio', 'punto_desembarque': 'Terminal de llegada',
      'estado': 'PENDIENTE'},
  ],
};

class ApiAbordajePrueba extends SismocApi {
  final DatosAbordaje detalle = detallePrueba();
  int cambios = 0;
  bool falla = false;
  @override
  Future<Map<String, dynamic>> post(String action, Map<String, dynamic> body) async {
    if (falla) throw ApiError('Sin conexión de prueba', 0);
    if (action == 'panel_abordaje') {
      return {'hoy': '2026-11-25', 'operario': 'OPERARIO DE PRUEBA',
        'viajes': [
          {...detalle['viaje'] as Map, 'registrados': 1, 'abordados': cambios,
            'pendientes': cambios == 0 ? 1 : 0},
        ]};
    }
    if (action == 'abordaje') return detalle;
    if (action == 'embarcar') {
      expect(body['identidad_verificada'], true);
      expect(body['anterior'], 'PENDIENTE');
      expect(body['pasajero'], 4);
      expect(body['viaje'], 1);
      expect(body['estado'], 'EMBARCADO');
      cambios++;
      detalle['pasajeros'][0]['estado'] = 'EMBARCADO';
      return {'mensaje': 'Guardado en servidor de prueba.'};
    }
    throw StateError('Acción no prevista: $action');
  }
}

void main() {
  testWidgets('Panel usa viajes reales y abre la lista sin crear viajes locales', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = ApiAbordajePrueba();
    await tester.pumpWidget(MaterialApp(home: PanelAbordaje(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('Panel de Abordaje'), findsOneWidget);
    expect(find.text('Hoy 1'), findsOneWidget);
    expect(find.text('Mañana 0'), findsOneWidget);
    expect(find.textContaining('DEMO'), findsNothing);
    await tester.scrollUntilVisible(find.text('Abordaje'), 250,
      scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Abordaje'));
    await tester.pumpAndSettle();
    expect(find.text('Manifiesto y Embarque'), findsOneWidget);
    expect(find.text('PASAJERO DE PRUEBA\nBOLETO-01'), findsOneWidget);
    expect(api.cambios, 0);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Manifiesto mantiene documento completo con desplazamiento horizontal', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: ManifiestoViaje(datos: detallePrueba())));
    await tester.pumpAndSettle();
    expect(find.text('MANIFIESTO DE PASAJEROS'), findsOneWidget);
    expect(find.textContaining('20456789123'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Texto ampliado no desborda el panel en teléfono', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(1.4)),
        child: child!),
      home: PanelAbordaje(api: ApiAbordajePrueba())));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('Validación manual exige identidad y persiste mediante API', (tester) async {
    final api = ApiAbordajePrueba();
    await tester.pumpWidget(MaterialApp(home: ManifiestoEmbarque(api: api, viajeId: 1)));
    await tester.pumpAndSettle();
    final campo = find.byWidgetPredicate((w) =>
      w is TextField && w.decoration?.labelText == 'Código de boleto');
    await tester.scrollUntilVisible(campo, 250,
      scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.enterText(campo, 'BOLETO-01');
    await tester.scrollUntilVisible(find.text('Validar Boleto'), 250,
      scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Validar Boleto'));
    await tester.pumpAndSettle();
    final confirmar = find.widgetWithText(FilledButton, 'Confirmar');
    expect(tester.widget<FilledButton>(confirmar).onPressed, isNull);
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.tap(confirmar);
    await tester.pumpAndSettle();
    expect(api.cambios, 1);
    expect(api.detalle['pasajeros'][0]['estado'], 'EMBARCADO');
    expect(tester.takeException(), isNull);
  });

  testWidgets('Código ajeno al viaje no registra embarques', (tester) async {
    final api = ApiAbordajePrueba();
    await tester.pumpWidget(MaterialApp(home: ManifiestoEmbarque(api: api, viajeId: 1)));
    await tester.pumpAndSettle();
    final campo = find.byWidgetPredicate((w) =>
      w is TextField && w.decoration?.labelText == 'Código de boleto');
    await tester.scrollUntilVisible(campo, 250,
      scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.enterText(campo, 'OTRO-VIAJE');
    await tester.scrollUntilVisible(find.text('Validar Boleto'), 250,
      scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Validar Boleto'));
    await tester.pumpAndSettle();
    expect(api.cambios, 0);
    expect(find.textContaining('Código no encontrado'), findsOneWidget);
  });

  testWidgets('Viaje cerrado deja control de boletos deshabilitado', (tester) async {
    final api = ApiAbordajePrueba();
    api.detalle['puede_modificar'] = false;
    await tester.pumpWidget(MaterialApp(home: ManifiestoEmbarque(api: api, viajeId: 1)));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Validar Boleto'), 250,
      scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    final validar = find.ancestor(of: find.text('Validar Boleto'),
      matching: find.byWidgetPredicate((w) => w is FilledButton));
    expect(tester.widget<FilledButton>(validar).onPressed, isNull);
    expect(api.cambios, 0);
  });

  test('PDF genera documento real multipágina sin datos ficticios incrustados', () async {
    final datos = detallePrueba();
    final plantilla = DatosAbordaje.from(datos['pasajeros'][0]);
    datos['pasajeros'] = List.generate(130, (i) => {
      ...plantilla, 'id': i + 1, 'asiento': i + 1, 'nombre': 'PASAJERO PRUEBA $i',
    });
    final bytes = await generarPdfReal(datos, PdfPageFormat.a4);
    expect(utf8.decode(bytes.take(5).toList()), '%PDF-');
    expect(bytes.length, greaterThan(1000));
  });
}
