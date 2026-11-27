import 'package:flutter/material.dart';

class PasswordField extends StatefulWidget {
  final TextEditingController controller;
  final String label;
  final bool enabled;
  final ValueChanged<String>? onSubmitted;
  final IconData? prefixIcon;
  final String? hintText;
  final TextInputAction? textInputAction;
  const PasswordField(
      {super.key,
      required this.controller,
      required this.label,
      this.enabled = true,
      this.onSubmitted,
      this.prefixIcon,
      this.hintText,
      this.textInputAction});
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
      textInputAction: widget.textInputAction,
      decoration: InputDecoration(
          labelText: widget.label,
          hintText: widget.hintText,
          prefixIcon: widget.prefixIcon == null
              ? null
              : Icon(widget.prefixIcon, size: 20),
          suffixIcon: IconButton(
              tooltip: hidden ? 'Mostrar contraseña' : 'Ocultar contraseña',
              onPressed: () => setState(() => hidden = !hidden),
              icon: Icon(hidden
                  ? Icons.visibility_outlined
                  : Icons.visibility_off_outlined))));
}
