/// Interfaz recuperada del panel de abordaje, conectada a operaciones reales.
/// No crea reservas, no simula escaneos ni modifica el estado local como éxito.
library;

import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:uuid/uuid.dart';
import 'api.dart';

typedef DatosAbordaje = Map<String, dynamic>;
typedef AbrirCroquis = Future<void> Function(DatosAbordaje viaje);
const _acento = Color(0xffef681f);
const _texto = Color(0xff0f172a);
const _suave = Color(0xff64748b);
const _borde = Color(0xffe2e8f0);
const _fondo = Color(0xfff6f8fb);
const _verde = Color(0xff16a34a);
const _navy = Color(0xff1e293b);

String _dato(dynamic v) =>
    v == null || '$v'.trim().isEmpty ? 'No registrado' : '$v';
String _fecha(String valor) {
  final d = DateTime.tryParse(valor);
  return d == null ? valor : '${d.day.toString().padLeft(2, '0')}/'
      '${d.month.toString().padLeft(2, '0')}/${d.year}';
}
String _larga(String valor) {
  final d = DateTime.tryParse(valor);
  if (d == null) return valor;
  const dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
  const meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  return '${dias[d.weekday - 1]}, ${d.day} de ${meses[d.month - 1]} de ${d.year}';
}
String _estado(dynamic v) => switch (v) {
  'PROGRAMADO' => 'Programado',
  'EN_CURSO' => 'En curso',
  'FINALIZADO' => 'Finalizado',
  'EMBARCADO' => 'A bordo',
  'DESEMBARCADO' => 'Desembarcado',
  'NO_PRESENTADO' => 'No presentado',
  'CANCELADO' => 'Cancelado',
  _ => 'Pendiente',
};

Widget _tarjeta(List<Widget> hijos) => Container(
  width: double.infinity,
  margin: const EdgeInsets.only(bottom: 16),
  padding: const EdgeInsets.all(18),
  decoration: BoxDecoration(
    color: Colors.white, border: Border.all(color: _borde),
    borderRadius: BorderRadius.circular(16),
  ),
  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: hijos),
);

Widget _titulo(String s) => Text(s, style: const TextStyle(
  fontWeight: FontWeight.w800, fontSize: 18, color: _texto));

Widget _contador(String titulo, int numero, Color color, IconData icono,
    {String? sufijo}) => Expanded(child: Container(
  padding: const EdgeInsets.all(12),
  decoration: BoxDecoration(color: Colors.white, border: Border.all(color: _borde),
    borderRadius: BorderRadius.circular(16)),
  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Icon(icono, color: color, size: 23),
    const SizedBox(height: 8),
    Text(titulo, style: const TextStyle(fontSize: 10, color: _suave,
      fontWeight: FontWeight.w700)),
    Text('$numero${sufijo ?? ''}', style: TextStyle(
      fontSize: 23, color: color, fontWeight: FontWeight.w800)),
  ]),
));

class PanelAbordaje extends StatefulWidget {
  final SismocApi api;
  final bool embedded;
  final AbrirCroquis? onCroquis;
  const PanelAbordaje({super.key, required this.api, this.embedded = false,
    this.onCroquis});
  @override
  State<PanelAbordaje> createState() => _PanelAbordajeState();
}

class _PanelAbordajeState extends State<PanelAbordaje> {
  List<DatosAbordaje> viajes = [];
  String hoy = '', operario = '', busqueda = '', filtro = 'TODOS', error = '', mes = '';
  bool cargando = true;
  int grupo = 0;
  @override
  void initState() { super.initState(); cargar(); }
  Future<void> cargar() async {
    try {
      final r = await widget.api.panelAbordaje(
          grupo == 2 && mes.isNotEmpty ? mes : null);
      if (!mounted) return;
      setState(() {
        viajes = (r['viajes'] as List).map((v) => DatosAbordaje.from(v)).toList();
        hoy = r['hoy']; operario = r['operario'];
        mes = r['mes'] ?? mes;
        cargando = false; error = '';
      });
    } catch (e) {
      if (mounted) setState(() {
        cargando = false; error = e is ApiError ? e.message : 'No se pudo actualizar el panel. Revisa tu conexión.';
      });
    }
  }
  String get manana {
    final d = DateTime.tryParse(hoy);
    return d == null ? '' : d.add(const Duration(days: 1)).toIso8601String().substring(0, 10);
  }
  List<DatosAbordaje> get visibles => viajes.where((v) =>
    (grupo == 2 || v['fecha'] == (grupo == 0 ? hoy : manana)) &&
    (filtro == 'TODOS' || v['estado'] == filtro) &&
    '${v['id']} ${v['bus']} ${v['origen']} ${v['destino']}'
      .toLowerCase().contains(busqueda.toLowerCase())).toList();
  Future<void> abrir(DatosAbordaje v) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) =>
      ManifiestoEmbarque(api: widget.api, viajeId: v['id'],
        onCroquis: widget.onCroquis)));
    await cargar();
  }
  Future<void> elegirMes() async {
    final inicial = DateTime.tryParse('$mes-01') ?? DateTime.now();
    final elegido = await showDialog<DateTime>(context: context, builder: (ctx) {
      var anio = inicial.year;
      return StatefulBuilder(builder: (ctx, cambiar) => AlertDialog(
        title: const Text('Seleccionar mes'),
        content: SizedBox(width: 300, child: Column(mainAxisSize: MainAxisSize.min, children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            IconButton(onPressed: () => cambiar(() => anio--), icon: const Icon(Icons.chevron_left)),
            Text('$anio', style: const TextStyle(fontWeight: FontWeight.w700)),
            IconButton(onPressed: () => cambiar(() => anio++), icon: const Icon(Icons.chevron_right)),
          ]),
          const SizedBox(height: 8),
          GridView.count(crossAxisCount: 4, shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            children: [
              for (var m = 1; m <= 12; m++)
                TextButton(
                  onPressed: () => Navigator.pop(ctx, DateTime(anio, m)),
                  child: Text(['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][m - 1]),
                ),
            ],
          ),
        ])),
      ));
    });
    if (elegido == null || !mounted) return;
    setState(() => mes = '${elegido.year}-${elegido.month.toString().padLeft(2, '0')}');
    await cargar();
  }
  Future<void> filtros() async {
    final elegido = await showModalBottomSheet<String>(context: context,
      builder: (ctx) => SafeArea(child: Column(mainAxisSize: MainAxisSize.min,
        children: [
          for (final e in {'TODOS': 'Todos los estados', 'PROGRAMADO': 'Programados',
            'EN_CURSO': 'En curso', 'FINALIZADO': 'Finalizados'}.entries)
            RadioListTile<String>(value: e.key, groupValue: filtro,
              title: Text(e.value), onChanged: (v) => Navigator.pop(ctx, v)),
        ])));
    if (elegido != null && mounted) setState(() => filtro = elegido);
  }
  @override
  Widget build(BuildContext context) {
    final lista = visibles;
    final body = RefreshIndicator(onRefresh: cargar, child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16), children: [
        if (cargando) const LinearProgressIndicator(),
        if (error.isNotEmpty) _tarjeta([
          Text(error, style: const TextStyle(color: Colors.red)),
          const Text('La información puede estar desactualizada.'),
          TextButton(onPressed: cargar, child: const Text('Reintentar')),
        ]),
        SegmentedButton<int>(segments: [
          ButtonSegment(value: 0, label: Text('Hoy ${viajes.where((v) => v['fecha'] == hoy).length}')),
          ButtonSegment(value: 1, label: Text('Mañana ${viajes.where((v) => v['fecha'] == manana).length}')),
          ButtonSegment(value: 2, label: Text('Todos ${viajes.length}')),
        ], selected: {grupo}, onSelectionChanged: (s) {
          setState(() => grupo = s.first);
          cargar();
        }),
        const SizedBox(height: 18),
        if (grupo == 2)
          _tarjeta([Row(children: [
            Container(width: 34, height: 34,
              decoration: BoxDecoration(color: const Color(0xffffefe5),
                borderRadius: BorderRadius.circular(10)),
              child: const Icon(Icons.calendar_month_outlined,
                color: _acento, size: 18)),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('CONSULTAR VIAJES POR MES', style: TextStyle(color: _suave, fontSize: 10,
                fontWeight: FontWeight.w700)),
              Text(mes.isEmpty ? 'Cargando…' : mes,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            ])),
            IconButton(onPressed: elegirMes,
              tooltip: 'Cambiar mes', icon: const Icon(Icons.calendar_month_outlined,
                color: _acento)),
          ])]),
        const SizedBox(height: 12),
        const SizedBox(height: 16),
        Row(children: [
          Expanded(child: TextField(onChanged: (s) => setState(() => busqueda = s),
            decoration: const InputDecoration(hintText: 'Buscar...', prefixIcon: Icon(Icons.search)))),
          const SizedBox(width: 8),
          OutlinedButton.icon(onPressed: filtros, icon: const Icon(Icons.filter_list),
            label: Text(filtro == 'TODOS' ? 'Filtros' : _estado(filtro))),
        ]),
        const SizedBox(height: 16),
        for (final v in lista) _viaje(v),
        if (!cargando && lista.isEmpty) _tarjeta([
          const Text('No hay viajes asignados que coincidan con esta consulta.'),
        ]),
        Text('Mostrando ${lista.length} ${lista.length == 1 ? 'viaje' : 'viajes'}',
          style: const TextStyle(color: _suave)),
        const SizedBox(height: 12),
        const Text('● 100% abordado    ● En progreso    ● Sin pasajeros',
          style: TextStyle(fontSize: 11, color: _suave)),
      ]));
    return widget.embedded ? ColoredBox(color: _fondo, child: body) :
      Scaffold(backgroundColor: _fondo, appBar: AppBar(title: const Text('Panel de Abordaje')),
        body: body);
  }
  Widget _viaje(DatosAbordaje v) {
    final n = v['registrados'] as int, a = v['abordados'] as int;
    final capacidad = v['capacidad'] as int?;
    final ocupados = (v['ocupados'] ?? n) as int;
    return _tarjeta([
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('●  ${v['origen']}', style: const TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text('○  ${v['destino']}', style: const TextStyle(color: _suave)),
        ])),
        Chip(label: Text(_estado(v['estado'])),
          backgroundColor: const Color(0xffeff6ff)),
      ]),
      const Divider(height: 28),
      Text('▣  ${v['bus']}    ${_fecha(v['fecha'])}, ${v['hora']}',
        style: const TextStyle(fontWeight: FontWeight.w600)),
      const SizedBox(height: 10),
      Wrap(spacing: 8, children: [
        Chip(label: Text(capacidad == null ? 'Capacidad sin confirmar' :
          '${(capacidad - ocupados).clamp(0, capacidad)} libres'),
          backgroundColor: const Color(0xffeefbf3)),
        Chip(label: Text('$ocupados ocupados'),
          backgroundColor: const Color(0xffffeeee)),
      ]),
      const SizedBox(height: 12),
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        const Text('ABORDAJE', style: TextStyle(color: _suave, fontSize: 11)),
        Text('${n == 0 ? 0 : (a * 100 / n).round()}%'),
      ]),
      const SizedBox(height: 8),
      LinearProgressIndicator(value: n == 0 ? 0 : a / n, color: _verde,
        backgroundColor: const Color(0xfff1f5f9)),
      const SizedBox(height: 8),
      Text('$a de $n pasajeros a bordo', style: const TextStyle(color: _suave)),
      Align(alignment: Alignment.centerRight, child: OutlinedButton.icon(
        onPressed: () => abrir(v), icon: const Icon(Icons.chevron_right),
        label: const Text('Abordaje'))),
    ]);
  }
}

class ManifiestoEmbarque extends StatefulWidget {
  final SismocApi api;
  final int viajeId;
  final AbrirCroquis? onCroquis;
  const ManifiestoEmbarque({super.key, required this.api, required this.viajeId,
    this.onCroquis});
  @override
  State<ManifiestoEmbarque> createState() => _ManifiestoEmbarqueState();
}

class _ManifiestoEmbarqueState extends State<ManifiestoEmbarque> {
  DatosAbordaje? detalle;
  String error = '', buscar = '';
  bool cargando = true, guardando = false, conectado = false;
  final codigo = TextEditingController();
  List<DatosAbordaje> get pasajeros => ((detalle?['pasajeros'] ?? []) as List)
    .map((p) => DatosAbordaje.from(p)).toList();
  bool get editable => conectado && detalle?['puede_modificar'] == true && !guardando;
  @override
  void initState() { super.initState(); cargar(); }
  @override
  void dispose() { codigo.dispose(); super.dispose(); }
  Future<void> cargar() async {
    try {
      final r = await widget.api.post('abordaje', {'viaje': widget.viajeId});
      if (mounted) setState(() {
        detalle = r; error = ''; conectado = true; cargando = false;
      });
    } catch (e) {
      if (mounted) setState(() {
        if (e is ApiError && (e.status == 401 || e.status == 403)) detalle = null;
        error = e is ApiError ? e.message : 'Sin conexión. Actualiza antes de registrar un embarque.';
        conectado = false; cargando = false;
      });
    }
  }
  void aviso(String texto) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(texto)));
  }
  Future<void> verificar(DatosAbordaje p, {bool boleto = false}) async {
    if (!editable) return;
    bool identidad = false;
    String estado = p['estado'] == 'EMBARCADO' ? 'DESEMBARCADO' : 'EMBARCADO';
    final nuevo = await showDialog<String>(context: context, builder: (ctx) =>
      StatefulBuilder(builder: (ctx, cambiar) => AlertDialog(
        title: Text('Piso ${p['piso']} · Asiento ${p['asiento']}'),
        content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${p['nombre']}\nDocumento: ${p['documento']}\n'
              'Boleto: ${p['referencia']}\nSube: ${_dato(p['punto'])}\n'
              'Baja: ${_dato(p['punto_desembarque'] ?? p['destino'])}\n'
              'Estado: ${_estado(p['estado'])}'),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(initialValue: estado,
              items: [
                if (p['estado'] != 'EMBARCADO')
                  const DropdownMenuItem(value: 'EMBARCADO', child: Text('Embarcar')),
                if (!boleto && p['estado'] == 'EMBARCADO')
                  const DropdownMenuItem(value: 'DESEMBARCADO', child: Text('Desembarcar')),
                if (!boleto && p['estado'] == 'PENDIENTE')
                  const DropdownMenuItem(value: 'NO_PRESENTADO', child: Text('No presentado')),
              ], onChanged: (v) => cambiar(() => estado = v!)),
            if (estado == 'EMBARCADO') CheckboxListTile(
              contentPadding: EdgeInsets.zero, value: identidad,
              title: const Text('Verifiqué identidad y boleto'),
              onChanged: (v) => cambiar(() => identidad = v ?? false)),
          ])),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
          FilledButton(onPressed: estado == 'EMBARCADO' && !identidad ? null :
            () => Navigator.pop(ctx, estado), child: const Text('Confirmar')),
        ],
      )));
    if (nuevo == null || !mounted) return;
    setState(() => guardando = true);
    try {
      final r = await widget.api.post('embarcar', {
        'id': const Uuid().v4(), 'viaje': widget.viajeId, 'pasajero': p['id'],
        'anterior': p['estado'], 'estado': nuevo, 'identidad_verificada': identidad,
      });
      codigo.clear();
      aviso(r['mensaje'] ?? 'Estado guardado en el servidor.');
    } catch (e) {
      aviso(e is ApiError ? e.message : 'No se confirmó el cambio. Actualiza la lista antes de reintentar.');
    } finally {
      await cargar();
      if (mounted) setState(() => guardando = false);
    }
  }
  Future<void> validarCodigo(String texto) async {
    if (!editable) return;
    final limpio = texto.trim().toUpperCase();
    if (limpio.isEmpty) { aviso('Ingresa o escanea el código del boleto.'); return; }
    await cargar();
    if (!mounted || !editable) return;
    final coincidencias = pasajeros.where((p) =>
      '${p['referencia']}'.trim().toUpperCase() == limpio).toList();
    if (coincidencias.length != 1) {
      aviso('Código no encontrado en este viaje. Usa la referencia de boleto registrada por Ventas.');
      return;
    }
    final p = coincidencias.single;
    if (p['estado'] == 'EMBARCADO') { aviso('Este boleto ya está a bordo.'); return; }
    if (p['estado'] == 'CANCELADO' || p['estado'] == 'DESEMBARCADO') {
      aviso('Este boleto está cerrado.'); return;
    }
    await verificar(p, boleto: true);
  }
  Future<void> escanear() async {
    if (!editable) return;
    final leido = await Navigator.push<String>(context,
      MaterialPageRoute(builder: (_) => const EscanerBoleto()));
    if (leido != null && mounted) await validarCodigo(leido);
  }
  @override
  Widget build(BuildContext context) {
    final ps = pasajeros.where((p) => p['estado'] != 'CANCELADO').toList();
    final abordaron = ps.where((p) => p['estado'] == 'EMBARCADO').length;
    final pendientes = ps.where((p) => p['estado'] == 'PENDIENTE').length;
    final porcentaje = ps.isEmpty ? 0 : (100 * abordaron / ps.length).round();
    final viaje = detalle?['viaje'] as Map? ?? {};
    final encontrados = pasajeros.where((p) =>
      '${p['nombre']} ${p['documento']} ${p['referencia']} ${p['punto']} ${p['asiento']}'
        .toLowerCase().contains(buscar.toLowerCase())).toList();
    return Scaffold(backgroundColor: _fondo,
      appBar: AppBar(title: const Text('Manifiesto y Embarque'), actions: [
        IconButton(onPressed: guardando ? null : cargar, icon: const Icon(Icons.sync),
          tooltip: 'Actualizar pasajeros'),
      ]),
      body: RefreshIndicator(onRefresh: cargar, child: ListView(
        physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.all(16),
        children: [
          if (cargando || guardando) const LinearProgressIndicator(),
          if (error.isNotEmpty) _tarjeta([Text(error,
            style: const TextStyle(color: Colors.red)),
            TextButton(onPressed: cargar, child: const Text('Reintentar'))]),
          if (detalle != null) ...[
            Text('${viaje['origen']} a ${viaje['destino']} | Bus: ${viaje['bus']}',
              style: const TextStyle(color: _suave)),
            const SizedBox(height: 16),
            FilledButton.icon(style: FilledButton.styleFrom(backgroundColor: _navy),
              onPressed: !conectado ? null : () async {
                await cargar();
                if (!context.mounted || !conectado) return;
                await Navigator.push(context, MaterialPageRoute(builder: (_) =>
                  ManifiestoViaje(datos: detalle!)));
              }, icon: const Icon(Icons.description_outlined),
              label: const Text('Ver Manifiesto SUTRAN')),
            const SizedBox(height: 16),
            _tarjeta([
              _titulo('Lista de Pasajeros'),
              const SizedBox(height: 12),
              TextField(onChanged: (s) => setState(() => buscar = s),
                decoration: const InputDecoration(hintText: 'Buscar por nombre, DNI o punto de recojo',
                  prefixIcon: Icon(Icons.search))),
              const SizedBox(height: 10),
              if (pasajeros.isEmpty)
                const Text('Ventas todavía no cargó la lista de pasajeros.'),
              SingleChildScrollView(scrollDirection: Axis.horizontal, child: DataTable(
                columnSpacing: 18, dataRowMinHeight: 64, dataRowMaxHeight: 88,
                columns: const [
                  DataColumn(label: Text('ASIENTO')), DataColumn(label: Text('PASAJERO')),
                  DataColumn(label: Text('DNI')), DataColumn(label: Text('ABORDAJE')),
                  DataColumn(label: Text('RECOJO / BAJADA')),
                ],
                rows: encontrados.map((p) => DataRow(cells: [
                  DataCell(Text('${p['asiento']}\nPiso ${p['piso']}',
                    style: const TextStyle(color: _acento, fontWeight: FontWeight.bold))),
                  DataCell(SizedBox(width: 170, child: Text('${p['nombre']}\n${p['referencia']}'))),
                  DataCell(Text('${p['documento']}')),
                  DataCell(OutlinedButton.icon(
                    onPressed: editable && p['estado'] != 'CANCELADO' &&
                      p['estado'] != 'DESEMBARCADO' ? () => verificar(p) : null,
                    icon: Icon(p['estado'] == 'EMBARCADO' ? Icons.check_circle_outline : Icons.person_outline,
                      color: p['estado'] == 'EMBARCADO' ? _verde : _suave, size: 18),
                    label: Text(_estado(p['estado'])))),
                  DataCell(SizedBox(width: 190, child: Text(
                    'Sube: ${_dato(p['punto'])}\nBaja: ${_dato(p['punto_desembarque'] == '' ? p['destino'] : p['punto_desembarque'])}'))),
                ])).toList(),
              )),
              const Text('Desliza la tabla para ver los puntos de recojo y bajada.',
                style: TextStyle(color: _suave, fontSize: 11)),
            ]),
            _tarjeta([
              _titulo('Progreso del Viaje'), const SizedBox(height: 14),
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                const Text('Porcentaje a bordo'), Text('$porcentaje%',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              ]),
              const SizedBox(height: 12),
              LinearProgressIndicator(value: ps.isEmpty ? 0 : abordaron / ps.length,
                color: _verde, backgroundColor: const Color(0xfff1f5f9)),
              const SizedBox(height: 16),
              Row(children: [
                _contador('A BORDO', abordaron, _verde, Icons.check_circle_outline),
                const SizedBox(width: 10),
                _contador('PENDIENTES', pendientes, _texto, Icons.people_outline),
              ]),
            ]),
            if (!editable) _tarjeta([
              const Text('Solo consulta: el viaje está cerrado, es histórico o no hay conexión.'),
            ]),
            _tarjeta([
              Row(children: [const Icon(Icons.qr_code, color: _acento),
                const SizedBox(width: 8), Expanded(child: _titulo('Control de Boletos (QR)'))]),
              const SizedBox(height: 10),
              const Text('Escanea el QR del boleto o ingresa su código. '
                'Debe coincidir con la referencia que Ventas cargó en este viaje.',
                style: TextStyle(color: _suave)),
              const SizedBox(height: 12),
              SizedBox(width: double.infinity, child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: _navy),
                onPressed: editable ? escanear : null,
                icon: const Icon(Icons.photo_camera_outlined),
                label: const Text('Escanear con cámara'))),
              const SizedBox(height: 16),
              const Center(child: Text('O MANUAL', style: TextStyle(color: _suave))),
              const SizedBox(height: 12),
              TextField(controller: codigo, enabled: editable,
                onSubmitted: editable ? validarCodigo : null,
                decoration: const InputDecoration(labelText: 'Código de boleto',
                  hintText: 'Referencia registrada por Ventas')),
              const SizedBox(height: 12),
              SizedBox(width: double.infinity, child: FilledButton.icon(
                onPressed: editable ? () => validarCodigo(codigo.text) : null,
                icon: const Icon(Icons.qr_code), label: const Text('Validar Boleto'))),
              const SizedBox(height: 10),
              const Text('Los cambios se confirman en el servidor. No se simulan abordajes.',
                style: TextStyle(color: _suave, fontSize: 11)),
            ]),
            if (widget.onCroquis != null) OutlinedButton.icon(
              onPressed: () async {
                await widget.onCroquis!({...DatosAbordaje.from(viaje),
                  'ruta': '${viaje['origen']} → ${viaje['destino']}',
                  'embarque': detalle!['puede_modificar'], 'asignado': true});
                await cargar();
              }, icon: const Icon(Icons.airline_seat_recline_normal),
              label: const Text('Ver croquis de asientos')),
          ],
        ])),
    );
  }
}

class EscanerBoleto extends StatefulWidget {
  const EscanerBoleto({super.key});
  @override
  State<EscanerBoleto> createState() => _EscanerBoletoState();
}
class _EscanerBoletoState extends State<EscanerBoleto> {
  final controller = MobileScannerController(formats: const [BarcodeFormat.qrCode]);
  bool terminado = false;
  @override
  void dispose() { controller.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Escanear boleto')),
    body: Column(children: [
      const Padding(padding: EdgeInsets.all(16),
        child: Text('Apunta al QR del boleto. Después deberás confirmar la identidad del pasajero.')),
      Expanded(child: MobileScanner(controller: controller,
        errorBuilder: (ctx, e) => Center(child: Padding(padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('No se pudo abrir la cámara. Revisa el permiso de cámara en Ajustes; también puedes usar el código manual.'),
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Volver')),
          ]))),
        onDetect: (capture) {
          if (terminado) return;
          for (final b in capture.barcodes) {
            if (b.rawValue?.trim().isNotEmpty == true) {
              terminado = true;
              Navigator.pop(context, b.rawValue);
              return;
            }
          }
        })),
    ]),
  );
}

/// El mismo diseño de manifiesto recuperado, sin identidad fiscal ficticia.
class ManifiestoViaje extends StatelessWidget {
  final DatosAbordaje datos;
  const ManifiestoViaje({super.key, required this.datos});
  @override
  Widget build(BuildContext context) {
    final v = datos['viaje'] as Map, empresa = datos['empresa'] as Map;
    final ps = (datos['pasajeros'] as List).where((p) => p['estado'] != 'CANCELADO').toList();
    final conductores = (v['conductores'] as List).where((c) => '${c['nombre']}'.isNotEmpty).toList();
    final responsables = (v['responsables'] as List).join(', ');
    return Scaffold(backgroundColor: _fondo,
      appBar: AppBar(title: const Text('Manifiesto SUTRAN')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Align(alignment: Alignment.centerLeft, child: TextButton.icon(
          onPressed: () => Navigator.pop(context), icon: const Icon(Icons.arrow_back),
          label: const Text('Regresar al Control de Embarque'))),
        FilledButton.icon(style: FilledButton.styleFrom(backgroundColor: _navy),
          onPressed: () async {
            try {
              await Printing.layoutPdf(name: 'manifiesto_${v['id']}.pdf',
                onLayout: (format) => generarPdfReal(datos, format));
            } catch (_) {
              if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('No se pudo imprimir el PDF. Inténtalo nuevamente.')));
            }
          }, icon: const Icon(Icons.print_outlined),
          label: const Text('IMPRIMIR MANIFIESTO (SUTRAN)')),
        const SizedBox(height: 16),
        _tarjeta([
          _titulo(_dato(empresa['nombre']).toUpperCase()),
          const SizedBox(height: 8),
          const Chip(label: Text('MANIFIESTO DE PASAJEROS')),
          Text('ID Viaje: #${v['id']}'),
          if ('${empresa['ruc'] ?? ''}'.isNotEmpty) Text('RUC: ${empresa['ruc']}'),
          if ('${empresa['direccion'] ?? ''}'.isNotEmpty) Text('${empresa['direccion']}'),
          const Divider(height: 30),
          Wrap(spacing: 22, runSpacing: 16, children: [
            _campo('VEHÍCULO (PLACA)', v['bus']),
            _campo('FECHA Y HORA SALIDA', '${_fecha(v['fecha'])}, ${v['hora']}'),
            _campo('RUTA DEL SERVICIO', '${v['origen']} → ${v['destino']}'),
            for (final c in conductores)
              _campo('CONDUCTOR / DNI', '${c['nombre']}\n${_dato(c['dni'])}'),
            _campo('CAPACIDAD DEL BUS', v['capacidad'] == null ?
              'Sin confirmar' : '${v['capacidad']} asientos'),
          ]),
          const SizedBox(height: 24),
          SingleChildScrollView(scrollDirection: Axis.horizontal, child: DataTable(
            headingRowColor: const WidgetStatePropertyAll(Color(0xfff1f5f9)),
            columns: const [
              DataColumn(label: Text('N°')), DataColumn(label: Text('ASIENTO')),
              DataColumn(label: Text('APELLIDOS Y NOMBRES')),
              DataColumn(label: Text('DOCUMENTO (DNI)')),
              DataColumn(label: Text('ESTADO')),
              DataColumn(label: Text('FIRMA / HUELLA')),
            ], rows: [
              for (var i = 0; i < ps.length; i++) DataRow(cells: [
                DataCell(Text('${i + 1}')), DataCell(Text('${ps[i]['asiento']} · Piso ${ps[i]['piso']}')),
                DataCell(Text('${ps[i]['nombre']}')), DataCell(Text('${ps[i]['documento']}')),
                DataCell(Text(_estado(ps[i]['estado']))), const DataCell(Text('')),
              ]),
            ])),
          const SizedBox(height: 22),
          Text('Total Pasajeros Registrados en Venta: ${ps.length}'),
          Text('Total Pasajeros a Bordo: ${ps.where((p) => p['estado'] == 'EMBARCADO').length}'),
          const SizedBox(height: 12),
          Text('Responsable de embarque asignado: ${responsables.isEmpty ? 'Sin asignación' : responsables}',
            style: const TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 36),
          const Text('____________________        ____________________\n'
            'FIRMA DEL CONDUCTOR         FIRMA DEL OPERARIO'),
          const SizedBox(height: 22),
          const Text('Manifiesto interno con datos del sistema. No acredita transmisión oficial al MTC ni autorización administrativa.',
            style: TextStyle(color: _suave, fontSize: 11)),
        ]),
      ]),
    );
  }
  Widget _campo(String etiqueta, dynamic valor) => SizedBox(width: 225,
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(etiqueta, style: const TextStyle(color: _suave, fontSize: 11)),
      const SizedBox(height: 4),
      Text(_dato(valor), style: const TextStyle(fontWeight: FontWeight.bold)),
    ]));
}

Future<Uint8List> generarPdfReal(DatosAbordaje datos, PdfPageFormat format) async {
  final v = datos['viaje'] as Map, empresa = datos['empresa'] as Map;
  final ps = (datos['pasajeros'] as List).where((p) => p['estado'] != 'CANCELADO').toList();
  final conductores = (v['conductores'] as List).where((c) => '${c['nombre']}'.isNotEmpty).toList();
  final responsables = (v['responsables'] as List).join(', ');
  final doc = pw.Document();
  doc.addPage(pw.MultiPage(
    pageFormat: format, margin: const pw.EdgeInsets.all(28),
    footer: (ctx) => pw.Column(children: [
      pw.Divider(),
      pw.Text('Manifiesto interno. No acredita transmisión oficial al MTC ni autorización administrativa.',
        style: const pw.TextStyle(fontSize: 8)),
      pw.Text('Página ${ctx.pageNumber} de ${ctx.pagesCount}', style: const pw.TextStyle(fontSize: 8)),
    ]),
    build: (_) => [
      pw.Text(_dato(empresa['nombre']).toUpperCase(),
        style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 18)),
      pw.Text('MANIFIESTO DE PASAJEROS - ID Viaje: #${v['id']}'),
      if ('${empresa['ruc'] ?? ''}'.isNotEmpty) pw.Text('RUC: ${empresa['ruc']}'),
      if ('${empresa['direccion'] ?? ''}'.isNotEmpty) pw.Text('${empresa['direccion']}'),
      pw.Divider(),
      pw.Text('VEHÍCULO: ${v['bus']}     SALIDA: ${_fecha(v['fecha'])}, ${v['hora']}'),
      pw.Text('RUTA DEL SERVICIO: ${v['origen']} - ${v['destino']}'),
      for (final c in conductores)
        pw.Text('CONDUCTOR: ${c['nombre']}   DNI: ${_dato(c['dni'])}'),
      pw.Text('CAPACIDAD: ${v['capacidad'] == null ? 'Sin confirmar' : '${v['capacidad']} asientos'}'),
      pw.SizedBox(height: 16),
      pw.TableHelper.fromTextArray(
        headerStyle: pw.TextStyle(fontSize: 8, fontWeight: pw.FontWeight.bold),
        cellStyle: const pw.TextStyle(fontSize: 8),
        headerDecoration: const pw.BoxDecoration(color: PdfColors.grey200),
        headers: ['N°', 'PISO / ASIENTO', 'APELLIDOS Y NOMBRES', 'DOCUMENTO', 'ESTADO', 'FIRMA / HUELLA'],
        data: [
          for (var i = 0; i < ps.length; i++) [
            '${i + 1}', '${ps[i]['piso']} / ${ps[i]['asiento']}',
            '${ps[i]['nombre']}', '${ps[i]['documento']}', _estado(ps[i]['estado']), '',
          ],
        ],
      ),
      pw.SizedBox(height: 18),
      pw.Text('Total Pasajeros Registrados en Venta: ${ps.length}'),
      pw.Text('Total Pasajeros a Bordo: ${ps.where((p) => p['estado'] == 'EMBARCADO').length}'),
      pw.Text('Responsable de embarque asignado: ${responsables.isEmpty ? 'Sin asignación' : responsables}'),
      pw.SizedBox(height: 40),
      pw.Row(mainAxisAlignment: pw.MainAxisAlignment.spaceAround, children: [
        pw.Text('____________________\nFIRMA DEL CONDUCTOR', style: const pw.TextStyle(fontSize: 9)),
        pw.Text('____________________\nFIRMA DEL OPERARIO', style: const pw.TextStyle(fontSize: 9)),
      ]),
    ],
  ));
  return doc.save();
}
