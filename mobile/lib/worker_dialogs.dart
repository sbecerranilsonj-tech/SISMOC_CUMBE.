import 'package:flutter/material.dart';

const _ink = Color(0xff172b45);
const _muted = Color(0xff7c899b);
const _orange = Color(0xfff26522);

String _dateLabel(dynamic value) {
  final date = DateTime.tryParse('$value');
  if (date == null) return '$value';
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
  return '${date.day} ${months[date.month - 1]} ${date.year}';
}

class WorkerDialogFrame extends StatelessWidget {
  const WorkerDialogFrame({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.content,
    required this.footer,
  });
  final String title, subtitle;
  final IconData icon;
  final Widget content, footer;

  @override
  Widget build(BuildContext context) => Dialog(
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: 420,
            maxHeight: MediaQuery.sizeOf(context).height * .85,
          ),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                      color: const Color(0xffffebdc),
                      borderRadius: BorderRadius.circular(12)),
                  child: Icon(icon, color: _orange, size: 21),
                ),
                const SizedBox(width: 10),
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text(title,
                          style: const TextStyle(
                              fontSize: 19,
                              fontWeight: FontWeight.w700,
                              color: _ink)),
                      const SizedBox(height: 4),
                      Text(subtitle,
                          style: const TextStyle(fontSize: 12, color: _muted)),
                    ])),
                IconButton(
                  tooltip: 'Cerrar',
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close, size: 20, color: _muted),
                  padding: EdgeInsets.zero,
                  constraints:
                      const BoxConstraints(minWidth: 36, minHeight: 38),
                ),
              ]),
              const SizedBox(height: 20),
              Flexible(child: SingleChildScrollView(child: content)),
              const SizedBox(height: 18),
              footer,
            ]),
          ),
        ),
      );
}

class NoticesDialog extends StatelessWidget {
  const NoticesDialog(
      {super.key, required this.notices, required this.approvals});
  final List<Map> notices, approvals;

  Widget heading(String title) => Padding(
        padding: const EdgeInsets.only(top: 5, bottom: 6),
        child: Align(
            alignment: Alignment.centerLeft,
            child: Text(title,
                style: const TextStyle(
                    fontSize: 11, fontWeight: FontWeight.w600, color: _muted))),
      );

  Widget notice(IconData icon, String title, String subtitle,
          {bool approved = false}) =>
      Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: Color(0xffedf1f5)))),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
                color: approved
                    ? const Color(0xffeaf5ef)
                    : const Color(0xfffff0e5),
                borderRadius: BorderRadius.circular(10)),
            child: Icon(icon,
                size: 18, color: approved ? const Color(0xff30845c) : _orange),
          ),
          const SizedBox(width: 10),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(title,
                    style: const TextStyle(
                        color: _ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w600)),
                if (subtitle.isNotEmpty) ...[
                  const SizedBox(height: 5),
                  Text(subtitle,
                      style: const TextStyle(color: _muted, fontSize: 12)),
                ],
              ])),
        ]),
      );

  @override
  Widget build(BuildContext context) => WorkerDialogFrame(
        title: 'Avisos',
        subtitle: 'Actualizaciones de tu asistencia',
        icon: Icons.notifications_none,
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          if (notices.isNotEmpty) ...[
            heading('AVISOS GENERALES'),
            for (final item in notices)
              notice(
                  item['leido'] == true
                      ? Icons.notifications_none
                      : Icons.notifications_active_outlined,
                  '${item['texto'] ?? ''}',
                  item['creado'] == null ? '' : _dateLabel(item['creado'])),
          ],
          if (approvals.isNotEmpty) ...[
            heading('APROBACIONES RECIENTES'),
            for (final item in approvals)
              notice(Icons.check, 'Jornada aprobada',
                  '${_dateLabel(item['fecha'])} · Contabilidad',
                  approved: true),
          ],
          if (notices.isEmpty && approvals.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 28),
              child: Text('Sin avisos.', style: TextStyle(color: _muted)),
            ),
        ]),
        footer: SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cerrar'),
          ),
        ),
      );
}

class NewRequestDialog extends StatefulWidget {
  const NewRequestDialog({super.key, required this.shifts, this.today});
  final List<Map> shifts;
  final DateTime? today;

  @override
  State<NewRequestDialog> createState() => _NewRequestDialogState();
}

class _NewRequestDialogState extends State<NewRequestDialog> {
  final form = GlobalKey<FormState>();
  final detail = TextEditingController();
  String type = 'PERMISO';
  int? shift;
  bool emergency = false;
  late DateTime from, until;
  String? dateError;
  static const types = {
    'PERMISO': 'Permiso',
    'VACACIONES': 'Vacaciones',
    'CAMBIO_HORARIO': 'Cambio de horario',
    'CORRECCION': 'Corrección',
  };

  @override
  void initState() {
    super.initState();
    final now = widget.today ?? DateTime.now();
    from = DateTime(now.year, now.month, now.day + 1);
    until = from;
  }

  @override
  void dispose() {
    detail.dispose();
    super.dispose();
  }

  String iso(DateTime date) =>
      '${date.year}-${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';
  String label(DateTime date) => '${date.day.toString().padLeft(2, '0')}/'
      '${date.month.toString().padLeft(2, '0')}/${date.year}';

  InputDecoration decoration(String title) => InputDecoration(
        labelText: title,
        filled: true,
        fillColor: const Color(0xfffcfdfe),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
        enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: Color(0xffdfe5ed))),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 13),
      );

  Future<void> choose(bool start) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: start ? from : until,
      firstDate: DateTime(2020),
      lastDate: DateTime(2035),
    );
    if (picked == null || !mounted) return;
    setState(() {
      if (start) {
        from = picked;
        if (until.isBefore(from)) until = from;
      } else {
        until = picked;
      }
      dateError = null;
    });
  }

  Widget dateField(String title, DateTime date, bool start) => OutlinedButton(
        onPressed: () => choose(start),
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.all(11),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          side: const BorderSide(color: Color(0xffdfe5ed)),
          foregroundColor: _ink,
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(color: _muted, fontSize: 12)),
          const SizedBox(height: 7),
          Row(children: [
            Expanded(
                child: Text(label(date), style: const TextStyle(fontSize: 12))),
            const SizedBox(width: 4),
            const Icon(Icons.calendar_month_outlined, size: 17, color: _muted),
          ]),
        ]),
      );

  void submit() {
    final valid = form.currentState!.validate();
    final rangeValid =
        !until.isBefore(from) && until.difference(from).inDays <= 366;
    setState(() => dateError = rangeValid
        ? null
        : 'Revisa las fechas: el rango debe ser válido y no superar 366 días.');
    if (!valid || !rangeValid) return;
    Navigator.pop(context, <String, dynamic>{
      'tipo': type,
      'datos': {if (type == 'CAMBIO_HORARIO') 'turno': shift},
      'desde': iso(from),
      'hasta': iso(until),
      'detalle': detail.text.trim(),
      'emergencia': emergency,
    });
  }

  @override
  Widget build(BuildContext context) => WorkerDialogFrame(
        title: 'Nueva solicitud',
        subtitle: 'Permisos y cambios de jornada',
        icon: Icons.event_note_outlined,
        content: Form(
            key: form,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              DropdownButtonFormField<String>(
                initialValue: type,
                isExpanded: true,
                decoration: decoration('Tipo de solicitud'),
                items: types.entries
                    .map((item) => DropdownMenuItem(
                        value: item.key, child: Text(item.value)))
                    .toList(),
                onChanged: (value) => setState(() => type = value!),
              ),
              if (type == 'CAMBIO_HORARIO') ...[
                const SizedBox(height: 16),
                DropdownButtonFormField<int>(
                  initialValue: shift,
                  isExpanded: true,
                  decoration: decoration('Turno solicitado'),
                  items: [
                    for (final item in widget.shifts)
                      DropdownMenuItem<int>(
                          value: item['id'],
                          child: Text('${item['nombre']}',
                              overflow: TextOverflow.ellipsis))
                  ],
                  validator: (value) =>
                      value == null ? 'Selecciona el turno solicitado.' : null,
                  onChanged: (value) => setState(() => shift = value),
                ),
              ],
              const SizedBox(height: 16),
              LayoutBuilder(builder: (context, constraints) {
                final dates = [
                  dateField('Desde', from, true),
                  dateField('Hasta', until, false)
                ];
                if (constraints.maxWidth < 270 ||
                    MediaQuery.textScalerOf(context).scale(12) > 16) {
                  return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        dates[0],
                        const SizedBox(height: 10),
                        dates[1]
                      ]);
                }
                return Row(children: [
                  Expanded(child: dates[0]),
                  const SizedBox(width: 10),
                  Expanded(child: dates[1]),
                ]);
              }),
              if (dateError != null)
                Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(dateError!,
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.error))),
              const SizedBox(height: 16),
              TextFormField(
                controller: detail,
                minLines: 3,
                maxLines: 5,
                maxLength: 2000,
                decoration: decoration('Motivo').copyWith(
                    hintText: 'Explica brevemente tu solicitud…',
                    alignLabelWithHint: true,
                    counterText: ''),
                validator: (value) => (value ?? '').trim().length < 5
                    ? 'Explica el motivo (mínimo 5 caracteres).'
                    : null,
              ),
              const SizedBox(height: 14),
              Material(
                color: const Color(0xfffff7f0),
                shape: RoundedRectangleBorder(
                    side: const BorderSide(color: Color(0xfff8e9dc)),
                    borderRadius: BorderRadius.circular(11)),
                child: SwitchListTile(
                  value: emergency,
                  onChanged: (value) => setState(() => emergency = value),
                  dense: true,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 10),
                  title: const Text('Es una emergencia',
                      style: TextStyle(fontSize: 13, color: Color(0xff7b4d32))),
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                  'Se enviará a revisión. No se aprueba automáticamente.',
                  style: TextStyle(color: _muted, fontSize: 12)),
            ])),
        footer: Row(children: [
          Expanded(
              child: OutlinedButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancelar'))),
          const SizedBox(width: 8),
          Expanded(
              child: FilledButton(
            onPressed: submit,
            style: FilledButton.styleFrom(
                backgroundColor: _orange, foregroundColor: Colors.white),
            child: const Text('Enviar solicitud', textAlign: TextAlign.center),
          )),
        ]),
      );
}
