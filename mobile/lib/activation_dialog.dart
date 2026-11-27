import 'package:flutter/material.dart';
import 'api.dart';
import 'password_field.dart';

class ActivationDialog extends StatefulWidget {
  final SismocApi api;
  const ActivationDialog({super.key, required this.api});
  @override
  State<ActivationDialog> createState() => _ActivationDialogState();
}

class _ActivationDialogState extends State<ActivationDialog> {
  final activation = TextEditingController(),
      password = TextEditingController(),
      confirmation = TextEditingController();
  Map<String, dynamic>? verified;
  String error = '';
  bool busy = false;
  @override
  void dispose() {
    activation.dispose();
    password.dispose();
    confirmation.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy) return;
    if (verified == null && activation.text.trim().isEmpty) {
      setState(
          () => error = 'Ingrese el código de activación generado en la web.');
      return;
    }
    if (verified != null &&
        (password.text.length < 8 || password.text != confirmation.text)) {
      setState(() =>
          error = 'Use al menos 8 caracteres y repita la misma contraseña.');
      return;
    }
    setState(() {
      busy = true;
      error = '';
    });
    try {
      if (verified == null) {
        final result =
            await widget.api.verifyActivation(activation.text.trim());
        if (mounted) setState(() => verified = result);
      } else {
        await widget.api.finishActivation(
            verified!['ticket'], password.text, confirmation.text);
        if (mounted) Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted)
        setState(() => error = e is ApiError
            ? e.message
            : 'No se pudo conectar con SISMOC. Revise el servidor.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text(
            verified == null ? 'Activar mi cuenta' : 'Crear mi contraseña'),
        content: SingleChildScrollView(
            child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
              if (verified == null) ...[
                const Text(
                    'Ingrese únicamente el código temporal generado en el panel web. Su código de trabajador se asignará automáticamente.'),
                const SizedBox(height: 8),
                Text('Servidor: ${widget.api.base}',
                    style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 16),
                TextField(
                    controller: activation,
                    enabled: !busy,
                    autocorrect: false,
                    enableSuggestions: false,
                    decoration: const InputDecoration(
                        labelText: 'Código de activación'),
                    onSubmitted: (_) => submit()),
              ] else ...[
                Text(verified!['nombre'],
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                SelectableText('Código de trabajador: ${verified!['codigo']}'),
                const Text(
                    'Este celular recordará su código. Para ingresar usará solo su contraseña.'),
                const SizedBox(height: 16),
                PasswordField(
                    controller: password,
                    enabled: !busy,
                    label: 'Nueva contraseña (mínimo 8 caracteres)'),
                const SizedBox(height: 16),
                PasswordField(
                    controller: confirmation,
                    enabled: !busy,
                    label: 'Repetir contraseña',
                    onSubmitted: (_) => submit()),
              ],
              if (error.isNotEmpty)
                Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(error,
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.error))),
              if (busy)
                const Padding(
                    padding: EdgeInsets.only(top: 16),
                    child: LinearProgressIndicator()),
            ])),
        actions: [
          TextButton(
              onPressed: busy ? null : () => Navigator.pop(context, false),
              child: const Text('Cancelar')),
          FilledButton(
              onPressed: busy ? null : submit,
              child: Text(
                  verified == null ? 'Validar código' : 'Guardar contraseña'))
        ],
      );
}
