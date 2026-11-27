import 'package:flutter/material.dart';

const _orange = Color(0xfff26522);
const _navy = Color(0xff172b45);
const _muted = Color(0xff68788d);

String salesStatus(Map trip) => switch ('${trip['estado']}') {
      'PROGRAMADO' => 'Programado',
      'EN_CURSO' => 'En curso',
      'FINALIZADO' => 'Finalizado',
      'CANCELADO' => 'Cancelado',
      'ANULADO' => 'Anulado',
      'NO_PRESENTADO' => 'No presentado',
      _ => '${trip['estado'] ?? 'Sin estado'}',
    };

bool salesHistory(Map trip, DateTime now) {
  if (['FINALIZADO', 'CANCELADO', 'ANULADO', 'NO_PRESENTADO']
      .contains(trip['estado'])) {
    return true;
  }
  // Un viaje en curso sigue visible aunque haya cruzado la medianoche.
  if (trip['estado'] == 'EN_CURSO') return false;
  final date = DateTime.tryParse('${trip['fecha']}');
  return date != null && date.isBefore(DateTime(now.year, now.month, now.day));
}

String salesDate(Map trip) {
  final date = DateTime.tryParse('${trip['fecha']}');
  const months = [
    'ene',
    'feb',
    'mar',
    'abr',
    'may',
    'jun',
    'jul',
    'ago',
    'sep',
    'oct',
    'nov',
    'dic'
  ];
  final label = date == null
      ? '${trip['fecha'] ?? 'Sin fecha'}'
      : '${date.day} ${months[date.month - 1]} ${date.year}';
  final time = '${trip['hora'] ?? ''}';
  return '$label · ${time.length >= 5 ? time.substring(0, 5) : time}';
}

/// Ventas reutiliza las acciones existentes; este widget solo organiza su acceso.
class SalesTripsView extends StatefulWidget {
  const SalesTripsView({
    super.key,
    required this.trips,
    required this.onImport,
    required this.onBoarding,
    required this.onView,
    required this.onAssign,
    required this.onAssignBoarding,
    required this.onPassengers,
    required this.onIncident,
    this.canManage = true,
    this.busy = false,
    this.today,
  });

  final List<Map> trips;
  final VoidCallback onImport, onBoarding;
  final ValueChanged<Map> onView,
      onAssign,
      onAssignBoarding,
      onPassengers,
      onIncident;
  final bool canManage, busy;
  final DateTime? today;

  @override
  State<SalesTripsView> createState() => _SalesTripsViewState();
}

class _SalesTripsViewState extends State<SalesTripsView> {
  bool history = false;
  String search = '';

  void manage(String action, Map trip) {
    switch (action) {
      case 'drivers':
        widget.onAssign(trip);
      case 'boarding':
        widget.onAssignBoarding(trip);
      case 'passengers':
        widget.onPassengers(trip);
      case 'incident':
        widget.onIncident(trip);
    }
  }

  PopupMenuItem<String> action(String value, IconData icon, String label) =>
      PopupMenuItem(
        value: value,
        child: Row(children: [
          Icon(icon, size: 19, color: _muted),
          const SizedBox(width: 10),
          Flexible(child: Text(label)),
        ]),
      );

  Widget tripCard(Map trip) {
    final underway = trip['estado'] == 'EN_CURSO';
    final finished = trip['estado'] == 'FINALIZADO';
    final cancelled =
        ['CANCELADO', 'ANULADO', 'NO_PRESENTADO'].contains(trip['estado']);
    final tone = cancelled
        ? _muted
        : underway
            ? const Color(0xff176b82)
            : finished
                ? const Color(0xff28734f)
                : const Color(0xff946019);
    final incidents = (trip['incidencias'] as List? ?? []).length;
    final points = (trip['puntos'] as List? ?? []).join(', ');
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(17),
        side: const BorderSide(color: Color(0xffe3e8ee)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
                child: Text('${trip['ruta'] ?? ''}',
                    style: const TextStyle(
                        color: _navy,
                        fontSize: 17,
                        fontWeight: FontWeight.w700))),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              decoration: BoxDecoration(
                  color: tone.withValues(alpha: .09),
                  borderRadius: BorderRadius.circular(7)),
              child: Text(salesStatus(trip),
                  style: TextStyle(
                      color: tone, fontSize: 11, fontWeight: FontWeight.w600)),
            ),
          ]),
          const SizedBox(height: 10),
          Text(salesDate(trip),
              style: const TextStyle(color: _navy, fontSize: 13)),
          const SizedBox(height: 5),
          Row(children: [
            const Icon(Icons.directions_bus_outlined, size: 16, color: _muted),
            const SizedBox(width: 6),
            Expanded(
                child: Text('${trip['bus'] ?? 'Sin placa'}',
                    style: const TextStyle(color: _muted, fontSize: 12))),
          ]),
          const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Divider(height: 1, color: Color(0xffedf0f4))),
          const Text('CONDUCTORES',
              style: TextStyle(
                  color: _muted, fontSize: 10, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          for (final key in ['conductor_1', 'conductor_2'])
            Text(
                '${trip[key] ?? ''}'.trim().isEmpty
                    ? 'Sin asignar'
                    : '${trip[key]}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                    color: Color(0xff415269), fontSize: 12, height: 1.5)),
          const SizedBox(height: 8),
          Text('Pasajeros: ${trip['pasajeros'] ?? 'sin información'}',
              style: const TextStyle(color: _muted, fontSize: 12)),
          if (points.isNotEmpty)
            Text('Embarques: $points',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: _muted, fontSize: 12)),
          if (incidents > 0)
            Text(
                '$incidents ${incidents == 1 ? 'incidencia registrada' : 'incidencias registradas'}',
                style: const TextStyle(color: _muted, fontSize: 12)),
          const SizedBox(height: 14),
          Row(children: [
            Expanded(
                child: FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: _orange,
                foregroundColor: Colors.white,
                minimumSize: const Size(0, 46),
                padding: const EdgeInsets.symmetric(horizontal: 12),
              ),
              onPressed: widget.busy ? null : () => widget.onView(trip),
              child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Flexible(child: Text('Ver viaje')),
                    SizedBox(width: 8),
                    Icon(Icons.arrow_forward, size: 17),
                  ]),
            )),
            if (widget.canManage) ...[
              const SizedBox(width: 8),
              PopupMenuButton<String>(
                enabled: !widget.busy,
                tooltip: 'Gestionar viaje',
                onSelected: (value) => manage(value, trip),
                itemBuilder: (_) => [
                  action(
                      'drivers', Icons.people_outline, 'Asignar conductores'),
                  if (['PROGRAMADO', 'EN_CURSO'].contains(trip['estado']))
                    action(
                        'boarding', Icons.badge_outlined, 'Asignar embarcador'),
                  action('passengers', Icons.upload_file_outlined,
                      'Cargar pasajeros'),
                  action('incident', Icons.report_outlined,
                      'Reportar incidencia o gasto'),
                ],
                child: Container(
                  constraints: const BoxConstraints(minHeight: 46),
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  decoration: BoxDecoration(
                      border: Border.all(color: const Color(0xffdce3eb)),
                      borderRadius: BorderRadius.circular(10)),
                  child: const Row(children: [
                    Text('Gestionar',
                        style: TextStyle(color: _muted, fontSize: 12)),
                    SizedBox(width: 2),
                    Icon(Icons.expand_more, size: 17, color: _muted),
                  ]),
                ),
              ),
            ],
          ]),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final now = widget.today ?? DateTime.now();
    final trips = widget.trips.where((trip) {
      if (salesHistory(trip, now) != history) return false;
      return '${trip['ruta']} ${trip['bus']} ${trip['conductor_1']} ${trip['conductor_2']}'
          .toLowerCase()
          .contains(search.toLowerCase().trim());
    }).toList()
      ..sort((a, b) {
        final order = '${a['fecha']} ${a['hora']}'
            .compareTo('${b['fecha']} ${b['hora']}');
        return history ? -order : order;
      });
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      LayoutBuilder(
          builder: (context, constraints) => Row(children: [
                Expanded(
                    child: Row(children: [
                  if (constraints.maxWidth >= 340)
                    Flexible(
                        child: TextButton.icon(
                      onPressed: widget.busy ? null : widget.onBoarding,
                      icon: const Icon(Icons.airline_seat_recline_normal,
                          size: 18),
                      label: const Text('Abordaje',
                          overflow: TextOverflow.ellipsis),
                      style: TextButton.styleFrom(
                          foregroundColor: _muted,
                          padding: const EdgeInsets.symmetric(horizontal: 8)),
                    ))
                  else
                    IconButton(
                      tooltip: 'Panel de abordaje',
                      onPressed: widget.busy ? null : widget.onBoarding,
                      icon: const Icon(Icons.airline_seat_recline_normal,
                          size: 20, color: _muted),
                    ),
                  if (constraints.maxWidth >= 340)
                    IconButton(
                      tooltip: 'Sobre la carga de itinerarios',
                      constraints:
                          const BoxConstraints(minWidth: 32, minHeight: 48),
                      padding: const EdgeInsets.all(5),
                      icon: const Icon(Icons.info_outline,
                          size: 18, color: _muted),
                      onPressed: () => showDialog<void>(
                          context: context,
                          builder: (ctx) => AlertDialog(
                                title: const Text('Carga de itinerarios'),
                                content: const Text(
                                    'Se comparan las salidas del Excel. Los conflictos se conservan '
                                    'para revisión y no se reemplazan viajes en curso.'),
                                actions: [
                                  TextButton(
                                      onPressed: () => Navigator.pop(ctx),
                                      child: const Text('Cerrar'))
                                ],
                              )),
                    ),
                ])),
                if (widget.canManage)
                  Expanded(
                      flex: 3,
                      child: Align(
                          alignment: Alignment.centerRight,
                          child: OutlinedButton.icon(
                            key: const ValueKey('sales-upload'),
                            onPressed: widget.busy ? null : widget.onImport,
                            icon: const Icon(Icons.upload_file_outlined,
                                size: 18),
                            label: const Text('Subir itinerarios',
                                maxLines: 2, style: TextStyle(fontSize: 12)),
                            style: OutlinedButton.styleFrom(
                                foregroundColor: const Color(0xffa34415),
                                padding:
                                    const EdgeInsets.symmetric(horizontal: 10),
                                side:
                                    const BorderSide(color: Color(0xffe8d4c7))),
                          ))),
              ])),
      const SizedBox(height: 8),
      SegmentedButton<bool>(
        segments: const [
          ButtonSegment(value: false, label: Text('Pendientes')),
          ButtonSegment(value: true, label: Text('Historial')),
        ],
        selected: {history},
        showSelectedIcon: false,
        onSelectionChanged: (value) => setState(() => history = value.first),
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.resolveWith((states) =>
              states.contains(WidgetState.selected)
                  ? const Color(0xffa34415)
                  : _muted),
          backgroundColor: WidgetStateProperty.resolveWith((states) =>
              states.contains(WidgetState.selected)
                  ? const Color(0xffffeadc)
                  : Colors.white),
        ),
      ),
      const SizedBox(height: 12),
      TextField(
        onChanged: (value) => setState(() => search = value),
        decoration: InputDecoration(
          hintText: 'Buscar ruta o placa',
          prefixIcon: const Icon(Icons.search, size: 21, color: _muted),
          filled: true,
          fillColor: Colors.white,
          contentPadding: const EdgeInsets.symmetric(vertical: 12),
          border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Color(0xffe3e8ee))),
          enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Color(0xffe3e8ee))),
        ),
      ),
      const SizedBox(height: 14),
      if (trips.isEmpty)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 30, horizontal: 12),
          child: Text(
              search.trim().isNotEmpty
                  ? 'No hay viajes para esta búsqueda.'
                  : history
                      ? 'No hay viajes en el historial disponible.'
                      : 'No hay viajes pendientes en el período disponible.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: _muted)),
        ),
      for (final trip in trips) tripCard(trip),
    ]);
  }
}
