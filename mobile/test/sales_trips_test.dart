import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sismoc_movil/sales_trips.dart';

final pending = <String, dynamic>{
  'id': 101,
  'ruta': 'CHICLAYO → JAÉN',
  'bus': 'B4E-954',
  'fecha': '2026-11-27',
  'hora': '06:30:00',
  'estado': 'PROGRAMADO',
  'conductor_1': 'RODRIGUEZ CABANILLAS RAUL BERARDO',
  'conductor_2': 'BRAVO QUIÑONES JUAN EDILBERTO',
  'pasajeros': null,
  'puntos': <String>[],
  'incidencias': <Map>[],
};
final finished = <String, dynamic>{
  ...pending,
  'id': 102,
  'ruta': 'JAÉN → CHICLAYO',
  'fecha': '2026-11-25',
  'estado': 'FINALIZADO',
};

Widget screen({
  bool canManage = true,
  VoidCallback? onImport,
  ValueChanged<Map>? onView,
  ValueChanged<Map>? onAssign,
  ValueChanged<Map>? onBoarding,
  ValueChanged<Map>? onPassengers,
  ValueChanged<Map>? onIncident,
}) =>
    MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: SalesTripsView(
        trips: [finished, pending],
        today: DateTime(2026, 11, 27),
        canManage: canManage,
        onImport: onImport ?? () {},
        onBoarding: () {},
        onView: onView ?? (_) {},
        onAssign: onAssign ?? (_) {},
        onAssignBoarding: onBoarding ?? (_) {},
        onPassengers: onPassengers ?? (_) {},
        onIncident: onIncident ?? (_) {},
      ),
    )));

void main() {
  testWidgets('Pendientes compactos, sin filas vacías ni botones repetidos',
      (tester) async {
    await tester.pumpWidget(screen());
    expect(find.text('CHICLAYO → JAÉN'), findsOneWidget);
    expect(find.text('JAÉN → CHICLAYO'), findsNothing);
    expect(find.text('Pasajeros: sin información'), findsOneWidget);
    expect(find.text('Embarques:'), findsNothing);
    expect(find.text('Ver viaje'), findsOneWidget);
    expect(find.text('Asignar conductores'), findsNothing);
    expect(find.text('Asignar embarcador'), findsNothing);
  });

  testWidgets('Historial y búsqueda conservan los datos reales',
      (tester) async {
    await tester.pumpWidget(screen());
    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();
    expect(find.text('JAÉN → CHICLAYO'), findsOneWidget);
    expect(find.text('CHICLAYO → JAÉN'), findsNothing);
    await tester.enterText(find.byType(TextField), 'placa inexistente');
    await tester.pump();
    expect(find.text('No hay viajes para esta búsqueda.'), findsOneWidget);
  });

  testWidgets('Gestionar conserva las cuatro acciones del viaje',
      (tester) async {
    final calls = <String>[];
    await tester.pumpWidget(screen(
      onAssign: (trip) => calls.add('conductores:${trip['id']}'),
      onBoarding: (trip) => calls.add('embarcador:${trip['id']}'),
      onPassengers: (trip) => calls.add('pasajeros:${trip['id']}'),
      onIncident: (trip) => calls.add('incidencia:${trip['id']}'),
    ));
    for (final label in [
      'Asignar conductores',
      'Asignar embarcador',
      'Cargar pasajeros',
      'Reportar incidencia o gasto'
    ]) {
      await tester.tap(find.text('Gestionar'));
      await tester.pumpAndSettle();
      await tester.tap(find.text(label));
      await tester.pumpAndSettle();
    }
    expect(calls, [
      'conductores:101',
      'embarcador:101',
      'pasajeros:101',
      'incidencia:101'
    ]);
  });

  testWidgets('Subir itinerarios queda al borde derecho y Ver viaje funciona',
      (tester) async {
    var imports = 0;
    Map? viewed;
    await tester.pumpWidget(
        screen(onImport: () => imports++, onView: (trip) => viewed = trip));
    final upload = find.byKey(const ValueKey('sales-upload'));
    expect(tester.getBottomRight(upload).dx,
        closeTo(tester.getSize(find.byType(Scaffold)).width - 16, 1));
    await tester.tap(upload);
    await tester.tap(find.text('Ver viaje'));
    expect(imports, 1);
    expect(viewed?['id'], 101);
  });

  testWidgets('Gerente solo consulta sin importar ni gestionar',
      (tester) async {
    await tester.pumpWidget(screen(canManage: false));
    expect(find.text('Subir itinerarios'), findsNothing);
    expect(find.text('Gestionar'), findsNothing);
    expect(find.text('Ver viaje'), findsOneWidget);
  });

  testWidgets('Diseño sin desbordes en pantalla estrecha y texto ampliado',
      (tester) async {
    tester.view.physicalSize = const Size(320, 900);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 1.3;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(screen());
  });

  test('Viajes en curso no se archivan por cruzar medianoche', () {
    expect(
        salesHistory({...pending, 'fecha': '2026-11-26', 'estado': 'EN_CURSO'},
            DateTime(2026, 11, 27)),
        isFalse);
  });
}
