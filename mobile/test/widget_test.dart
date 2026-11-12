import 'package:flutter_test/flutter_test.dart';
import 'package:sismoc_movil/main.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter/material.dart';
import 'package:sismoc_movil/password_field.dart';

void main() {
  testWidgets('El ojo permite mostrar y ocultar la contraseña sin modificarla',
      (tester) async {
    final controller = TextEditingController(text: 'PruebaSegura123!');
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: PasswordField(controller: controller, label: 'Contraseña'))));
    expect(
        tester.widget<TextField>(find.byType(TextField)).obscureText, isTrue);
    await tester.tap(find.byTooltip('Mostrar contraseña'));
    await tester.pump();
    expect(
        tester.widget<TextField>(find.byType(TextField)).obscureText, isFalse);
    expect(controller.text, 'PruebaSegura123!');
    await tester.tap(find.byTooltip('Ocultar contraseña'));
    await tester.pump();
    expect(
        tester.widget<TextField>(find.byType(TextField)).obscureText, isTrue);
  });
  testWidgets('Sin cuenta activada muestra ingreso y servidor de pruebas', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    await tester.pumpWidget(const SismocApp());
    await tester.pumpAndSettle();
    expect(find.text('Ingresar'), findsNothing);
    expect(find.text('Activar mi cuenta'), findsOneWidget);
    expect(find.text('Primera activación'), findsNothing);
    expect(find.text('Servidor de pruebas'), findsOneWidget);
  });
  testWidgets('Activar cuenta abre popup con un solo código temporal',
      (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    await tester.pumpWidget(const SismocApp());
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Activar mi cuenta'));
    await tester.tap(find.text('Activar mi cuenta'));
    await tester.pumpAndSettle();
    expect(find.text('Código de activación'), findsOneWidget);
    expect(find.text('Validar código'), findsOneWidget);
  });
}
