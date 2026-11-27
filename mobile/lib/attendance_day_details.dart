import 'package:flutter/material.dart';

/// Presentación de los datos diarios del sistema, sin inventar horas de ausencia.
class AttendanceDayDetails extends StatelessWidget {
  const AttendanceDayDetails({super.key, required this.day});

  final Map day;

  @override
  Widget build(BuildContext context) {
    if (day['solo_motivo'] == true) {
      final motivo = '${day['motivo_dia'] ?? ''}'.trim();
      final detalle = '${day['detalle_motivo'] ?? ''}'.trim();
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xffffede1),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(motivo.isEmpty ? 'Día no laborado' : motivo,
                style: const TextStyle(
                    color: Color(0xff873b16), fontWeight: FontWeight.w700)),
            if (detalle.isNotEmpty && detalle != motivo) ...[
              const SizedBox(height: 5),
              Text(detalle, style: const TextStyle(color: Color(0xff873b16))),
            ],
          ],
        ),
      );
    }
    final values = day['control_diario'] as Map?;
    if (values == null) return const SizedBox.shrink();
    return Column(
      children: [
        for (final item in [
          ('Horas trabajadas', 'trabajo'),
          ('Refrigerio', 'refrigerio'),
          ('Saldo de jornada', 'saldo'),
          ('Extras 25 %', 'he25'),
          ('Extras 35 %', 'he35'),
          ('Horas nocturnas', 'nocturnas'),
        ])
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: Row(children: [
              Expanded(child: Text(item.$1, style: const TextStyle(fontSize: 13))),
              Text('${values[item.$2] ?? '—'}',
                  style: const TextStyle(
                      fontSize: 13, fontWeight: FontWeight.w700)),
            ]),
          ),
      ],
    );
  }
}
