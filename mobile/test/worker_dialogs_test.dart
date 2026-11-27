import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sismoc_movil/worker_dialogs.dart';

Widget host(Widget dialog, {ValueChanged<dynamic>? onResult}) => MaterialApp(
      home: Scaffold(
          body: Builder(
              builder: (context) => TextButton(
                    onPressed: () async {
                      final result = await showDialog<dynamic>(
                          context: context, builder: (_) => dialog);
                      onResult?.call(result);
                    },
                    child: const Text('Abrir'),
                  ))),
    );

NewRequestDialog request() =>
    NewRequestDialog(today: DateTime(2026, 11, 27), shifts: const [
      {'id': 7, 'nombre': 'Mañana'}
    ]);

void main() {
  testWidgets('Solicitud conserva el contrato y solo se envía al confirmar',
      (tester) async {
    dynamic result;
    await tester
        .pumpWidget(host(request(), onResult: (value) => result = value));
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();
    expect(find.text('28/11/2026'), findsNWidgets(2));
    expect(result, isNull);
    await tester.enterText(
        find.byType(TextFormField), 'Permiso por motivo personal');
    await tester.ensureVisible(find.byType(SwitchListTile));
    await tester.tap(find.byType(SwitchListTile));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Enviar solicitud'));
    await tester.pumpAndSettle();
    expect(result, {
      'tipo': 'PERMISO',
      'datos': {},
      'desde': '2026-11-28',
      'hasta': '2026-11-28',
      'detalle': 'Permiso por motivo personal',
      'emergencia': true,
    });
  });

  testWidgets('Motivo obligatorio y Cancelar no devuelve solicitud',
      (tester) async {
    dynamic result = 'pendiente';
    await tester
        .pumpWidget(host(request(), onResult: (value) => result = value));
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Enviar solicitud'));
    await tester.pumpAndSettle();
    expect(
        find.text('Explica el motivo (mínimo 5 caracteres).'), findsOneWidget);
    expect(find.text('Nueva solicitud'), findsOneWidget);
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();
    expect(result, isNull);
  });

  testWidgets('Cambio de horario exige turno y conserva los cuatro tipos',
      (tester) async {
    await tester.pumpWidget(host(request()));
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    for (final label in [
      'Permiso',
      'Vacaciones',
      'Cambio de horario',
      'Corrección'
    ]) {
      expect(find.text(label), findsWidgets);
    }
    await tester.tap(find.text('Cambio de horario').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Enviar solicitud'));
    await tester.pumpAndSettle();
    expect(find.text('Selecciona el turno solicitado.'), findsOneWidget);
  });

  testWidgets('Avisos legibles con cierre fijo y lista desplazable',
      (tester) async {
    tester.view.physicalSize = const Size(360, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(host(NoticesDialog(
      notices: const [
        {'texto': 'Aviso real de prueba', 'leido': false}
      ],
      approvals: List.generate(30, (i) => {'fecha': '2026-08-23'}),
    )));
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();
    expect(find.text('Aviso real de prueba'), findsOneWidget);
    expect(find.text('Jornada aprobada'), findsWidgets);
    expect(find.text('23 ago 2026 · Contabilidad'), findsWidgets);
    await tester.tap(find.text('Cerrar'));
    await tester.pumpAndSettle();
    expect(find.text('Avisos'), findsNothing);
  });

  testWidgets('Avisos vacíos no inventan información', (tester) async {
    await tester
        .pumpWidget(host(const NoticesDialog(notices: [], approvals: [])));
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();
    expect(find.text('Sin avisos.'), findsOneWidget);
    expect(find.text('Jornada aprobada'), findsNothing);
  });

  testWidgets('Solicitud adaptable con texto grande y teclado abierto',
      (tester) async {
    tester.view.physicalSize = const Size(320, 740);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 1.3;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(host(request()));
    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();
    tester.view.viewInsets = const FakeViewPadding(bottom: 240);
    addTearDown(tester.view.resetViewInsets);
    await tester.pumpAndSettle();
    expect(find.text('Enviar solicitud'), findsOneWidget);
  });
}
