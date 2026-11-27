import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sismoc_movil/attendance_day_details.dart';

void main() {
  for (final motivo in ['Descanso semanal', 'Feriado no laborado', 'Permiso']) {
    testWidgets('$motivo muestra solo el motivo, sin conceptos de horas',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: AttendanceDayDetails(day: {
            'solo_motivo': true,
            'motivo_dia': motivo,
            'detalle_motivo': 'Registrado en el sistema',
            'control_diario': {'trabajo': 'Por revisar'},
          }),
        ),
      ));
      expect(find.text(motivo), findsOneWidget);
      expect(find.text('Registrado en el sistema'), findsOneWidget);
      for (final texto in [
        'Horas trabajadas', 'Refrigerio', 'Saldo de jornada',
        'Extras 25 %', 'Extras 35 %', 'Horas nocturnas', 'Por revisar',
      ]) {
        expect(find.text(texto), findsNothing);
      }
    });
  }
  testWidgets('Día trabajado conserva el detalle de horas', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: AttendanceDayDetails(day: {
          'solo_motivo': false,
          'control_diario': {'trabajo': '08:00:00', 'refrigerio': '01:00:00'},
        }),
      ),
    ));
    expect(find.text('Horas trabajadas'), findsOneWidget);
    expect(find.text('08:00:00'), findsOneWidget);
    expect(find.text('Refrigerio'), findsOneWidget);
  });
}
