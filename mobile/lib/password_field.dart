import 'package:flutter/material.dart';

class PasswordField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final bool enabled;
  final ValueChanged<String>? onSubmitted;
  const PasswordField(
      {super.key,
      required this.controller,
      required this.label,
      this.enabled = true,
      this.onSubmitted});
  @override
  State<PasswordField> createState() => _PasswordFieldState();
}

class _PasswordFieldState extends State<PasswordField> {
  bool hidden = true;
  @override
  Widget build(BuildContext context) => TextField(
      controller: widget.controller,
      enabled: widget.enabled,
      obscureText: hidden,
      autocorrect: false,
      enableSuggestions: false,
      onSubmitted: widget.onSubmitted,
      decoration: InputDecoration(
          labelText: widget.label,
          suffixIcon: IconButton(
              tooltip: hidden ? 'Mostrar contraseña' : 'Ocultar contraseña',
              onPressed: () => setState(() => hidden = !hidden),
              icon: Icon(hidden
                  ? Icons.visibility_outlined
                  : Icons.visibility_off_outlined))));
}
