import 'package:flutter/material.dart';

/// Reemplaza al recuadro rojo de Flutter cuando una vista no se puede dibujar.
/// Se registra desde main() con ErrorWidget.builder.
class PantallaError extends StatelessWidget {
  final VoidCallback onRestart;
  const PantallaError({super.key, required this.onRestart});

  @override
  Widget build(BuildContext context) => Directionality(
        textDirection: TextDirection.ltr,
        child: ColoredBox(
          color: const Color(0xfffaf7f4),
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 96,
                    height: 96,
                    decoration: const BoxDecoration(
                      color: Color(0xffffefe5),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.directions_bus_filled,
                      size: 48,
                      color: Color(0xfff26522),
                    ),
                  ),
                  const SizedBox(height: 22),
                  const Text(
                    'Algo salió mal',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      color: Color(0xff222222),
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'La app encontró un problema al mostrar esta pantalla. '
                    'Tu cuenta, tus viajes y tus datos no se pierden.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.45,
                      color: Color(0xff6f6f6f),
                    ),
                  ),
                  const SizedBox(height: 26),
                  GestureDetector(
                    onTap: onRestart,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 30, vertical: 15),
                      decoration: BoxDecoration(
                        color: const Color(0xfff26522),
                        borderRadius: BorderRadius.circular(9),
                      ),
                      child: const Text(
                        'VOLVER A INTENTAR',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.1,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Si el problema sigue, cierra la app y ábrela de nuevo.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: Color(0xff8a8a8a)),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
}
