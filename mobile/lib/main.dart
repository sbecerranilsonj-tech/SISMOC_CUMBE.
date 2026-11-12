import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';

import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:geolocator/geolocator.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:uuid/uuid.dart';

import 'api.dart';
import 'activation_dialog.dart';
import 'password_field.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SismocApp());
}

class SismocApp extends StatelessWidget {
  const SismocApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'SISMOC · El Cumbe',
        theme: ThemeData(
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xffc74d11)),
          scaffoldBackgroundColor: const Color(0xfff5f6fa),
          inputDecorationTheme: const InputDecorationTheme(
            border: OutlineInputBorder(),
          ),
        ),
        home: const Shell(),
      );
}

class Shell extends StatefulWidget {
  const Shell({super.key});
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  final api = SismocApi();
  final password = TextEditingController(), server = TextEditingController();
  bool loading = true, busy = false, offline = false;
  int tab = 0;
  String get role => api.data['perfil']?['rol'] ?? '';
  bool get driver => api.data['perfil']?['es_conductor'] == true;
  bool get canTrips => api.data['perfil']?['puede_ver_viajes'] == true;
  bool get sales => [
        'BOLETERIA',
        'CONTADORA',
        'ADMINISTRADOR',
        'GERENTE_GENERAL',
      ].contains(role);
  bool get manager =>
      ['CONTADORA', 'ADMINISTRADOR', 'GERENTE_GENERAL'].contains(role);
  @override
  void initState() {
    super.initState();
    start();
  }

  Future<void> start() async {
    await api.restore();
    server.text = api.base;
    if (api.token.isNotEmpty) {
      try {
        await api.refresh();
      } catch (_) {
        offline = true;
      }
    }
    if (mounted) setState(() => loading = false);
  }

  @override
  void dispose() {
    password.dispose();
    server.dispose();
    super.dispose();
  }

  void message(String text) {
    if (mounted)
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await action();
    } catch (e) {
      message(
        e is ApiError
            ? e.message
            : 'No se pudo conectar. Revise el servidor y la red.',
      );
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> refresh() async {
    try {
      await api.sync();
      await api.refresh();
      offline = false;
    } catch (_) {
      offline = true;
      rethrow;
    }
    if (mounted) setState(() {});
  }

  Future<void> send(String action, Map<String, dynamic> body) async {
    final result = await api.post(action, body);
    message(result['mensaje'] ?? 'Guardado.');
    await refresh();
  }

  Future<void> activateAccount() async {
    if (busy) return;
    api.base = server.text.trim().replaceAll(RegExp(r'/$'), '');
    final uri = Uri.tryParse(api.base);
    if (uri == null ||
        !['http', 'https'].contains(uri.scheme) ||
        uri.host.isEmpty) {
      message(
          'Ingrese la dirección completa del servidor, por ejemplo http://127.0.0.1:8000.');
      return;
    }
    await api.storage.write(key: 'base', value: api.base);
    if (!mounted) return;
    final activated = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => ActivationDialog(api: api));
    if (activated == true && mounted) {
      setState(() {
        password.clear();
        offline = false;
      });
      message('Contraseña creada. Inicia sesión con tu nueva contraseña.');
    }
  }

  Widget field(TextEditingController c, String label, {bool secret = false}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: secret
            ? PasswordField(controller: c, label: label)
            : TextField(
                controller: c,
                obscureText: secret,
                decoration: InputDecoration(labelText: label),
              ),
      );
  Widget box(String title, List<Widget> children) => Card(
        margin: const EdgeInsets.only(bottom: 16),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 14),
              ...children,
            ],
          ),
        ),
      );
  Widget button(String text, VoidCallback action, {IconData? icon}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: FilledButton.icon(
          onPressed: busy ? null : action,
          icon: Icon(icon ?? Icons.check),
          label: Text(text),
        ),
      );
  @override
  Widget build(BuildContext context) {
    if (loading)
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (api.token.isEmpty || api.data['perfil'] == null)
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(
                      Icons.directions_bus_filled,
                      size: 64,
                      color: Color(0xffc74d11),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      'EL CUMBE',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const Text(
                      'SISMOC · Tu jornada, en un lugar',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 28),
                    if (api.workerCode.isNotEmpty)
                      Padding(
                          padding: const EdgeInsets.only(bottom: 16),
                          child: Text('Código de trabajador: ${api.workerCode}',
                              textAlign: TextAlign.center))
                    else
                      const Padding(
                          padding: EdgeInsets.only(bottom: 16),
                          child: Text(
                              'Activa tu cuenta para vincular este celular.',
                              textAlign: TextAlign.center)),
                    if (api.workerCode.isNotEmpty)
                      field(password, 'Contraseña', secret: true),
                    ExpansionTile(
                      title: const Text('Servidor de pruebas'),
                      children: [field(server, 'URL de SISMOC')],
                    ),
                    if (api.workerCode.isNotEmpty)
                      button(
                        busy ? 'Conectando…' : 'Ingresar',
                        () => run(() async {
                          api.base = server.text.trim().replaceAll(
                                RegExp(r'/$'),
                                '',
                              );
                          final remembered = await api.storage
                                  .read(key: 'worker_code_${api.base}') ??
                              '';
                          if (remembered.isEmpty) {
                            message(
                                'Primero pulsa Activar mi cuenta y valida tu código temporal.');
                            return;
                          }
                          await api.login(
                            remembered,
                            password.text,
                            '',
                          );
                          password.clear();
                          offline = false;
                        }),
                        icon: Icons.login,
                      ),
                    OutlinedButton.icon(
                        onPressed: busy ? null : activateAccount,
                        icon: const Icon(Icons.key),
                        label: Text(api.workerCode.isEmpty
                            ? 'Activar mi cuenta'
                            : 'Activar otra cuenta')),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    final labels = [
      'Inicio',
      'Asistencia',
      role == 'OPERADOR_EMBARQUE' ? 'Embarque' : 'Viajes',
      'Solicitudes',
      'Mi cuenta',
    ];
    final sections = [0, if (!driver) 1, if (canTrips) 2, 3, 4];
    final currentTab = sections.contains(tab) ? tab : 0;
    return Scaffold(
      appBar: AppBar(
        title: Text(labels[currentTab]),
        actions: [
          IconButton(
            onPressed: busy ? null : () => run(refresh),
            icon: const Icon(Icons.sync),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: sections.indexOf(currentTab),
        onDestinationSelected: (v) => setState(() => tab = sections[v]),
        destinations: [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            label: 'Inicio',
          ),
          if (!driver)
            NavigationDestination(
              icon: Icon(Icons.fingerprint),
              label: 'Asistencia',
            ),
          if (canTrips)
            NavigationDestination(
              icon: Icon(Icons.directions_bus),
              label: role == 'OPERADOR_EMBARQUE' ? 'Embarque' : 'Viajes',
            ),
          NavigationDestination(
            icon: Icon(Icons.event_note),
            label: 'Solicitudes',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            label: 'Cuenta',
          ),
        ],
      ),
      body: Column(
        children: [
          if (busy) const LinearProgressIndicator(),
          if (offline)
            const MaterialBanner(
              content: Text(
                'Sin conexión · datos guardados. Algunas acciones requieren conexión.',
              ),
              actions: [SizedBox()],
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => run(refresh),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (currentTab == 0) ...home(),
                  if (currentTab == 1) ...attendance(),
                  if (currentTab == 2 && canTrips) ...trips(),
                  if (currentTab == 3) ...requests(),
                  if (currentTab == 4) ...account(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> home() {
    final p = api.data['perfil'];
    final r = api.data['resumen'] ?? {};
    return [
      Text(
        'Hola, ${p['nombre']}',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 16),
      if (driver)
        box('Mi período actual', [
          Text('Desde ${r['desde'] ?? ''}'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 24,
            runSpacing: 16,
            children: [
              metric('Trayectos', r['trayectos_realizados']),
              metric('Vueltas', r['vueltas']),
              metric('Estimado', 'S/ ${r['estimado']}'),
              metric('Pagado', 'S/ ${r['pagado']}'),
            ],
          ),
          const SizedBox(height: 12),
          Text('HORA ${r['HORA']} · X ${r['X']} · XX ${r['XX']}'),
          const Text(
            'Importes estimados por viajes finalizados. La aprobación y el pago se revisan en SISMOC.',
          ),
        ]),
      if (!driver)
        box('Mi asistencia del período', [
          Text('Desde ${r['desde'] ?? ''}'),
          const SizedBox(height: 12),
          Wrap(spacing: 24, runSpacing: 16, children: [
            metric('Jornadas', r['jornadas']),
            metric('Horas trabajadas', r['horas_trabajadas']),
            metric('Extras 25 %', r['horas_extras_25']),
            metric('Extras 35 %', r['horas_extras_35']),
            metric('Horas nocturnas', r['horas_nocturnas']),
          ]),
          const SizedBox(height: 12),
          Text(
              '${r['aprobadas'] ?? 0} jornadas aprobadas. Las horas calculadas están sujetas a revisión.'),
          button('Ver mi asistencia', () => setState(() => tab = 1),
              icon: Icons.fingerprint),
        ]),
      box('Notificaciones', [
        for (final n in (api.data['avisos'] ?? []) as List)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.notifications_outlined),
            title: Text(n['texto']),
            subtitle: Text(n['creado'].toString()),
            onTap: () => run(
              () => send('avisos', {
                'ids': [n['id']],
              }),
            ),
          ),
        if ((api.data['avisos'] ?? []).isEmpty)
          const Text('Sin notificaciones.'),
      ]),
    ];
  }

  Widget metric(String label, dynamic value) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${value ?? 0}',
              style: Theme.of(context).textTheme.headlineSmall),
          Text(label),
        ],
      );
  List<Widget> attendance() => [
        box('Marcar mi jornada', [
          const Text(
            'Ubícate en tu zona autorizada. El sistema comprobará la precisión del GPS. La hora válida se toma del servidor.',
          ),
          const SizedBox(height: 10),
          if (api.data['ausencia_hoy'] == true)
            const Text(
                'Tienes permiso o vacaciones aprobados para hoy. No corresponde marcar asistencia.'),
          if (api.data['comision_actual'] == true)
            const Text('Comisión vigente: puedes marcar sin ubicación.'),
          if (api.data['ausencia_hoy'] != true)
            for (final t in [
              'ENTRADA',
              'SALIDA_REFRIGERIO',
              'RETORNO_REFRIGERIO',
              'SALIDA',
            ])
              button(
                t.replaceAll('_', ' '),
                () => run(() => mark(t)),
                icon: Icons.my_location,
              ),
        ]),
        box('Mi horario', [
          for (final h in (api.data['horarios'] ?? []) as List)
            ListTile(title: Text(h['fecha']), subtitle: Text(h['turno'])),
          if ((api.data['horarios'] ?? []).isEmpty)
            const Text(
                'Sin programación publicada. Solicita revisar tu horario.'),
        ]),
        box('Marcaciones del mes', [
          for (final m in (api.data['marcaciones'] ?? []) as List)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(m['tipo'].toString().replaceAll('_', ' ')),
              subtitle: Text(
                '${m['recibido']}\n${m['estado']} ${m['motivo'] ?? ''}',
              ),
            ),
        ]),
        box('Horas y aprobación', [
          const Text(
            'Consulta las jornadas calculadas por SISMOC. Un registro recibido no significa que ya haya sido aprobado para pago.',
          ),
          for (final j in (api.data['jornadas'] ?? []) as List)
            ExpansionTile(
              title: Text('${j['fecha']} · ${j['estado'] ?? ''}'),
              children: [
                for (final entry in (j as Map).entries.where(
                      (e) =>
                          e.key.toString().contains('hora') ||
                          e.key.toString().contains('aprob'),
                    ))
                  ListTile(
                    title: Text(entry.key.toString().replaceAll('_', ' ')),
                    trailing: Text('${entry.value ?? 0}'),
                  ),
              ],
            ),
        ]),
      ];
  Future<void> mark(String type) async {
    if (!offline) {
      try {
        await api.refresh();
      } on ApiError catch (e) {
        if (e.status != 0) rethrow;
        offline = true;
      }
    }
    if (api.data['ausencia_hoy'] == true) {
      throw ApiError(
          'Tienes permiso o vacaciones aprobados para hoy. No corresponde marcar.',
          409);
    }
    final body = <String, dynamic>{
      'id': const Uuid().v4(),
      'tipo': type,
      'offline': offline,
    };
    if (api.data['comision_actual'] != true) {
      if (!await Geolocator.isLocationServiceEnabled()) {
        throw ApiError('Activa la ubicación del teléfono.', 422);
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        throw ApiError('Autoriza el acceso a ubicación al marcar.', 422);
      }
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 25)),
      );
      body.addAll({
        'gps_fecha': pos.timestamp.toUtc().toIso8601String(),
        'latitud': pos.latitude,
        'longitud': pos.longitude,
        'precision': pos.accuracy
      });
    }
    body['capturada'] = DateTime.now().toUtc().toIso8601String();
    try {
      await send('marcar', body);
      return;
    } on ApiError catch (e) {
      if (e.status != 0) rethrow;
    } catch (_) {}
    body['offline'] = true;
    await api.queue('marcar', body);
    offline = true;
    message(
        'Guardado en el teléfono. Se enviará para revisión al sincronizar.');
  }

  List<Widget> trips() => [
        if (sales)
          box('Ventas', [
            button(
              'Subir Excel de itinerarios',
              () => run(importTrips),
              icon: Icons.upload_file,
            ),
            const Text(
              'Se comparan las salidas. Los conflictos se conservan para revisión; no se reemplazan viajes en curso.',
            ),
          ]),
        for (final v in (api.data['viajes'] ?? []) as List)
          box('${v['fecha']} · ${v['hora']}', [
            Text(v['ruta'], style: Theme.of(context).textTheme.titleLarge),
            Text('${v['bus']} · ${v['estado']}'),
            Text('${v['conductor_1']}\n${v['conductor_2']}'),
            Text('Pasajeros reportados: ${v['pasajeros'] ?? 'No informado'}'),
            Text('Embarques: ${(v['puntos'] as List).join(', ')}'),
            const SizedBox(height: 8),
            if (v['asignado'] == true) ...[
              Text(v['disponibilidad']['mensaje']),
              if (v['estado'] == 'PROGRAMADO')
                button(
                  'Iniciar viaje · yo conduzco',
                  () => confirmEvent(v, 'INICIAR'),
                ),
              if (v['estado'] == 'EN_CURSO') ...[
                if (v['conduce'] == true)
                  button('Solicitar relevo', () => relevo(v)),
                if (v['relevo_pendiente'] == true)
                  button(
                    'Confirmar que tomo el relevo',
                    () => confirmEvent(v, 'ACEPTAR_RELEVO'),
                  ),
                button('Registrar llegada', () => confirmEvent(v, 'LLEGADA')),
              ],
              if (v['estado'] == 'FINALIZADO')
                button(
                  'Terminé labores · iniciar descanso',
                  () => confirmEvent(v, 'DESCANSO'),
                ),
            ],
            if (v['embarque'] == true)
              button(
                'Ver croquis y pasajeros',
                () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        Boarding(api: api, trip: Map<String, dynamic>.from(v)),
                  ),
                ),
                icon: Icons.airline_seat_recline_normal,
              ),
            button(
              'Reportar incidencia o gasto',
              () => incident(v),
              icon: Icons.report_outlined,
            ),
            if (sales) ...[
              button('Asignar conductores', () => assign(v)),
              if (v['estado'] == 'PROGRAMADO' || v['estado'] == 'EN_CURSO')
                button(
                    'Asignar responsable de embarque', () => assignBoarding(v)),
              button(
                'Subir lista CSV de pasajeros',
                () => run(() => importPassengers(v)),
              ),
            ],
            for (final i in v['incidencias'] as List)
              ListTile(
                title: Text('${i['tipo']} · ${i['estado']}'),
                subtitle: Text(i['descripcion']),
                onTap: sales
                    ? () => run(
                          () => send('resolver_incidencia', {
                            'id': i['id'],
                            'estado': 'RESUELTO',
                          }),
                        )
                    : null,
              ),
          ]),
        if ((api.data['viajes'] ?? []).isEmpty)
          box('Mis viajes', [
            const Text('No hay viajes asignados para este período.'),
          ]),
      ];
  Future<bool> confirm(String title, String text) async =>
      await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text(title),
          content: Text(text),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('Confirmar'),
            ),
          ],
        ),
      ) ??
      false;
  void confirmEvent(dynamic v, String type) async {
    if (await confirm(
      'Confirmar acción',
      type == 'DESCANSO'
          ? 'Confirmo que terminé mis labores y comienzo descanso fuera del bus.'
          : '${type.replaceAll('_', ' ')} en ${v['ruta']}. Se registrará la hora del servidor.',
    ))
      await run(
        () => send('evento', {
          'id': const Uuid().v4(),
          'viaje': v['id'],
          'tipo': type,
        }),
      );
  }

  Future<String?> input(String title, String label) async {
    final c = TextEditingController();
    final value = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: c,
          decoration: InputDecoration(labelText: label),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, c.text),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
    return value;
  }

  Future<void> relevo(dynamic v) async {
    if (v['companero_perfil'] == null) {
      message('El compañero todavía no tiene cuenta vinculada.');
      return;
    }
    if (await confirm(
      'Solicitar relevo',
      'El compañero asignado recibirá la solicitud. El cambio se registra cuando él lo acepte.',
    ))
      await run(
        () => send('evento', {
          'id': const Uuid().v4(),
          'viaje': v['id'],
          'tipo': 'SOLICITAR_RELEVO',
          'relevo': v['companero_perfil'],
        }),
      );
  }

  Future<void> incident(dynamic v) async {
    var tipo = 'AVERIA';
    final detail = TextEditingController(), amount = TextEditingController();
    final body = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, change) => AlertDialog(
          title: const Text('Incidencia o gasto'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: tipo,
                  items: [
                    'AVERIA',
                    'NEUMATICO',
                    'COMBUSTIBLE',
                    'DERRUMBE',
                    'SIN_PASE',
                    'DEMORA',
                    'OTRO',
                  ]
                      .map(
                        (t) => DropdownMenuItem(
                          value: t,
                          child: Text(t.replaceAll('_', ' ')),
                        ),
                      )
                      .toList(),
                  onChanged: (x) => change(() => tipo = x!),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: detail,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: '¿Qué ocurrió?'),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: amount,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Gasto S/ (opcional)',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, {
                'viaje': v['id'],
                'tipo': tipo,
                'descripcion': detail.text,
                'monto': amount.text,
              }),
              child: const Text('Reportar'),
            ),
          ],
        ),
      ),
    );
    if (body != null) await run(() => send('incidencia', body));
  }

  Future<void> importTrips() async {
    final picked = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['xls', 'xlsx'],
      withData: true,
    );
    if (picked == null) return;
    final f = picked.files.single;
    await send('importar_itinerario', {
      'nombre': f.name,
      'contenido': base64Encode(f.bytes ?? await File(f.path!).readAsBytes()),
    });
  }

  Future<void> importPassengers(dynamic v) async {
    final picked = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['csv'],
      withData: true,
    );
    if (picked == null) return;
    final f = picked.files.single;
    await send('importar_pasajeros', {
      'viaje': v['id'],
      'csv': utf8.decode(f.bytes ?? await File(f.path!).readAsBytes()),
    });
  }

  Future<void> assignBoarding(dynamic v) async {
    final options = ((api.data['embarcadores'] ?? []) as List)
        .where((e) =>
            e['conductor'] != true ||
            ((v['perfiles_conductores'] ?? []) as List).contains(e['id']))
        .toList();
    int? selected;
    bool allowDrivers = false;
    final body = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (ctx) => StatefulBuilder(
            builder: (ctx, change) => AlertDialog(
                    title: const Text('Responsable de embarque'),
                    content: Column(mainAxisSize: MainAxisSize.min, children: [
                      if (options.isEmpty)
                        const Text(
                            'Habilita primero una cuenta con función Encargado de embarque.'),
                      DropdownButtonFormField<int>(
                          isExpanded: true,
                          decoration:
                              const InputDecoration(labelText: 'Responsable'),
                          items: options
                              .map((e) => DropdownMenuItem<int>(
                                  value: e['id'],
                                  child: Text(e['nombre'],
                                      overflow: TextOverflow.ellipsis)))
                              .toList(),
                          onChanged: (x) => change(() => selected = x)),
                      CheckboxListTile(
                          value: allowDrivers,
                          title: const Text(
                              'Permitir también a los conductores asignados'),
                          onChanged: (x) => change(() => allowDrivers = x!)),
                    ]),
                    actions: [
                      TextButton(
                          onPressed: () => Navigator.pop(ctx),
                          child: const Text('Cancelar')),
                      FilledButton(
                          onPressed: selected == null
                              ? null
                              : () => Navigator.pop(ctx, {
                                    'viaje': v['id'],
                                    'perfil': selected,
                                    'conductores': allowDrivers
                                  }),
                          child: const Text('Asignar'))
                    ])));
    if (body != null) await run(() => send('asignar_embarque', body));
  }

  Future<void> assign(dynamic v) async {
    final options = api.data['conductores'] as List;
    int? one, two;
    var boarding = true;
    DateTime end = DateTime.now().add(const Duration(hours: 12));
    final body = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, change) => AlertDialog(
          title: const Text('Asignar conductores'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final number in [1, 2])
                  Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: DropdownButtonFormField<int>(
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: 'Conductor $number',
                      ),
                      items: options
                          .map(
                            (e) => DropdownMenuItem<int>(
                              value: e['id'] as int,
                              child: Text(
                                e['conductor__nombre'],
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (x) => change(() {
                        if (number == 1) {
                          one = x;
                        } else {
                          two = x;
                        }
                      }),
                    ),
                  ),
                ListTile(
                  title: const Text('Llegada prevista'),
                  subtitle: Text(end.toString().substring(0, 16)),
                  onTap: () async {
                    final day = await showDatePicker(
                      context: ctx,
                      firstDate: DateTime(2020),
                      lastDate: DateTime(2035),
                      initialDate: end,
                    );
                    if (day == null || !ctx.mounted) return;
                    final time = await showTimePicker(
                      context: ctx,
                      initialTime: TimeOfDay.fromDateTime(end),
                    );
                    if (time != null)
                      change(
                        () => end = DateTime(
                          day.year,
                          day.month,
                          day.day,
                          time.hour,
                          time.minute,
                        ),
                      );
                  },
                ),
                CheckboxListTile(
                  title: const Text('Conductores pueden verificar embarque'),
                  value: boarding,
                  onChanged: (x) => change(() => boarding = x!),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: one == null || two == null || one == two
                  ? null
                  : () => Navigator.pop(ctx, {
                        'viaje': v['id'],
                        'uno': one,
                        'dos': two,
                        'fin_previsto': end.toUtc().toIso8601String(),
                        'embarque_conductor': boarding,
                      }),
              child: const Text('Asignar'),
            ),
          ],
        ),
      ),
    );
    if (body != null) await run(() => send('asignar', body));
  }

  List<Widget> requests() => [
        box('Mis solicitudes', [
          const Text(
            'Permisos y cambios planificados: hasta el día anterior. Las emergencias se explican y pasan a revisión.',
          ),
          button('Nueva solicitud', newRequest, icon: Icons.add),
        ]),
        for (final s in (api.data['solicitudes'] ?? []) as List)
          box('${s['tipo']} · ${s['estado']}', [
            Text('${s['perfil__codigo']} · ${s['desde']} a ${s['hasta']}'),
            Text(s['detalle']),
            Text(s['respuesta'] ?? ''),
            if (manager && s['estado'] == 'PENDIENTE')
              Row(
                children: [
                  TextButton(
                    onPressed: () => reviewRequest(s),
                    child: const Text('Aprobar'),
                  ),
                  TextButton(
                    onPressed: () => run(
                      () => send('revisar_solicitud', {
                        'id': s['id'],
                        'aprobar': false,
                      }),
                    ),
                    child: const Text('Rechazar'),
                  ),
                ],
              ),
          ]),
      ];
  Future<void> reviewRequest(dynamic s) async {
    int? turno;
    if (s['tipo'] == 'CAMBIO_HORARIO') {
      turno = await showDialog<int>(
        context: context,
        builder: (ctx) => SimpleDialog(
          title: const Text('Horario confirmado'),
          children: [
            for (final t in (api.data['turnos'] ?? []) as List)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(ctx, t['id']),
                child: Text(t['nombre']),
              ),
          ],
        ),
      );
      if (turno == null) return;
    }
    if (await confirm(
      'Aprobar solicitud',
      'Se aplicará al período ${s['desde']} a ${s['hasta']}.',
    ))
      await run(
        () => send('revisar_solicitud', {
          'id': s['id'],
          'aprobar': true,
          'turno': turno,
        }),
      );
  }

  Future<void> newRequest() async {
    var tipo = 'PERMISO';
    int? requestedShift;
    var emergency = false;
    var from = DateTime.now().add(const Duration(days: 1));
    var until = from;
    final detail = TextEditingController();
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, change) => AlertDialog(
          title: const Text('Nueva solicitud'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: tipo,
                  items:
                      ['PERMISO', 'VACACIONES', 'CAMBIO_HORARIO', 'CORRECCION']
                          .map(
                            (t) => DropdownMenuItem(
                              value: t,
                              child: Text(t.replaceAll('_', ' ')),
                            ),
                          )
                          .toList(),
                  onChanged: (s) => change(() => tipo = s!),
                ),
                if (tipo == 'CAMBIO_HORARIO')
                  DropdownButtonFormField<int>(
                    initialValue: requestedShift,
                    decoration:
                        const InputDecoration(labelText: 'Turno solicitado'),
                    items: [
                      for (final t in (api.data['turnos'] ?? []) as List)
                        DropdownMenuItem<int>(
                            value: t['id'], child: Text(t['nombre']))
                    ],
                    onChanged: (v) => change(() => requestedShift = v),
                  ),
                ListTile(
                  title: Text('Desde: ${from.toString().substring(0, 10)}'),
                  onTap: () async {
                    final d = await showDatePicker(
                      context: ctx,
                      firstDate: DateTime(2020),
                      lastDate: DateTime(2035),
                      initialDate: from,
                    );
                    if (d != null) change(() => from = d);
                  },
                ),
                ListTile(
                  title: Text('Hasta: ${until.toString().substring(0, 10)}'),
                  onTap: () async {
                    final d = await showDatePicker(
                      context: ctx,
                      firstDate: DateTime(2020),
                      lastDate: DateTime(2035),
                      initialDate: until,
                    );
                    if (d != null) change(() => until = d);
                  },
                ),
                TextField(
                  controller: detail,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Detalle / motivo',
                  ),
                ),
                CheckboxListTile(
                  value: emergency,
                  onChanged: (v) => change(() => emergency = v!),
                  title: const Text('Es una emergencia'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: tipo == 'CAMBIO_HORARIO' && requestedShift == null
                  ? null
                  : () => Navigator.pop(ctx, {
                        'tipo': tipo,
                        'datos': {
                          if (tipo == 'CAMBIO_HORARIO') 'turno': requestedShift
                        },
                        'desde': from.toString().substring(0, 10),
                        'hasta': until.toString().substring(0, 10),
                        'detalle': detail.text,
                        'emergencia': emergency,
                      }),
              child: const Text('Enviar'),
            ),
          ],
        ),
      ),
    );
    if (result != null) await run(() => send('solicitud', result));
  }

  Future<void> showTestLocation() async {
    if (!await Geolocator.isLocationServiceEnabled())
      throw ApiError('Activa la ubicación del teléfono.', 422);
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied)
      permission = await Geolocator.requestPermission();
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever)
      throw ApiError('Autoriza el acceso a ubicación.', 422);
    final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 25)));
    if (!mounted) return;
    final coordinates =
        '${position.latitude.toStringAsFixed(7)}, ${position.longitude.toStringAsFixed(7)}';
    await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
                title: const Text('Mi ubicación para pruebas'),
                content: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SelectableText(
                          'Latitud: ${position.latitude.toStringAsFixed(7)}\nLongitud: ${position.longitude.toStringAsFixed(7)}\nPrecisión: ${position.accuracy.toStringAsFixed(0)} m'),
                      const SizedBox(height: 12),
                      const Text(
                          'En el panel web, crea una zona y elige Solo un trabajador. Copia estos valores y selecciona tu cuenta. Este botón no registra asistencia.'),
                    ]),
                actions: [
                  TextButton(
                      onPressed: () async {
                        await Clipboard.setData(
                            ClipboardData(text: coordinates));
                        if (ctx.mounted) Navigator.pop(ctx);
                      },
                      child: const Text('Copiar coordenadas')),
                  TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Cerrar'))
                ]));
  }

  List<Widget> account() => [
        box('Mi cuenta', [
          Text(api.data['perfil']['nombre']),
          Text('Código: ${api.data['perfil']['codigo']}'),
          Text('Área: ${api.data['perfil']['area'] ?? ''}'),
          const Text(
            'Las modificaciones de ficha, dispositivo y permisos las realiza la administración.',
          ),
        ]),
        if (!driver)
          box('Ubicación para pruebas', [
            const Text(
                'Obtén las coordenadas de este teléfono para configurar una zona de prueba solo para tu cuenta.'),
            button('Mi ubicación para pruebas', () => run(showTestLocation),
                icon: Icons.my_location),
          ]),
        box('Sincronización · ${api.pending.length} pendientes', [
          button('Enviar pendientes', () => run(refresh), icon: Icons.sync),
          for (final item in api.pending.where(
            (e) => e['account'] == api.data['perfil']['codigo'],
          ))
            ListTile(
              title: Text(item['action']),
              subtitle: Text(
                item['error'].toString().isEmpty ? 'Por enviar' : item['error'],
              ),
              trailing: IconButton(
                icon: const Icon(Icons.delete_outline),
                tooltip: 'Descartar intento pendiente',
                onPressed: () async {
                  if (await confirm(
                    'Descartar intento',
                    'Esta acción solo elimina este envío pendiente del teléfono. No modifica registros que ya recibió SISMOC.',
                  ))
                    await run(() async {
                      api.pending.remove(item);
                      await api.persistQueue();
                    });
                },
              ),
            ),
        ]),
        box('Pagos registrados', [
          for (final pago in (api.data['pagos'] ?? []) as List)
            ListTile(
              title: Text('S/ ${pago['monto']}'),
              subtitle: Text(
                '${pago['desde']} a ${pago['hasta']}',
              ),
            ),
        ]),
        button(
          'Cerrar sesión',
          () => run(() async {
            await api.logout();
          }),
          icon: Icons.logout,
        ),
      ];
}

class Boarding extends StatefulWidget {
  final SismocApi api;
  final Map<String, dynamic> trip;
  const Boarding({super.key, required this.api, required this.trip});
  @override
  State<Boarding> createState() => _BoardingState();
}

class _BoardingState extends State<Boarding> {
  List<dynamic> passengers = [];
  String search = '', error = '';
  bool busy = true;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    final cacheKey =
        'passengers_${widget.trip['id']}_${widget.api.data['perfil']['codigo']}';
    try {
      final d = await widget.api.post('pasajeros', {
        'viaje': widget.trip['id'],
      });
      passengers = d['pasajeros'];
      await widget.api.storage.write(
        key:
            'passengers_${widget.trip['id']}_${widget.api.data['perfil']['codigo']}',
        value: jsonEncode(passengers),
      );
      error = '';
    } on ApiError catch (e) {
      if (e.status == 401 || e.status == 403) {
        await widget.api.storage.delete(key: cacheKey);
        passengers = [];
        error = e.message;
      } else {
        final cached = await widget.api.storage.read(key: cacheKey);
        if (cached != null) passengers = jsonDecode(cached);
        error = e.message;
      }
    } catch (e) {
      final cached = await widget.api.storage.read(
        key:
            'passengers_${widget.trip['id']}_${widget.api.data['perfil']['codigo']}',
      );
      if (cached != null) {
        passengers = jsonDecode(cached);
        error =
            'Sin conexión · lista guardada. Las verificaciones quedarán pendientes de sincronización.';
      } else {
        error = e.toString();
      }
    }
    if (mounted) setState(() => busy = false);
  }

  Future<void> verify(dynamic p) async {
    var checked = false;
    var state = 'EMBARCADO';
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, change) => AlertDialog(
          title: Text('Asiento ${p['asiento']} · piso ${p['piso']}'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${p['nombre']}\nDocumento: ${p['documento']}\n${p['origen']} → ${p['destino']}\nSube: ${p['punto']}\nEstado: ${p['estado']}',
              ),
              DropdownButton<String>(
                value: state,
                items: ['EMBARCADO', 'NO_PRESENTADO', 'DESEMBARCADO']
                    .map((x) => DropdownMenuItem(value: x, child: Text(x)))
                    .toList(),
                onChanged: (v) => change(() => state = v!),
              ),
              CheckboxListTile(
                value: checked,
                onChanged: (v) => change(() => checked = v!),
                title: const Text('Verifiqué identidad y boleto'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Guardar'),
            ),
          ],
        ),
      ),
    );
    if (ok != true) return;
    final body = {
      'id': const Uuid().v4(),
      'viaje': widget.trip['id'],
      'pasajero': p['id'],
      'anterior': p['estado'],
      'estado': state,
      'identidad_verificada': checked,
    };
    try {
      await widget.api.post('embarcar', body);
      await load();
    } on ApiError catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      await load();
    } catch (_) {
      await widget.api.queue('embarcar', body);
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Verificación pendiente de sincronización. No está confirmada aún.',
            ),
          ),
        );
    }
  }

  Future<void> export() async {
    try {
      final result = await widget.api.post('manifiesto', {
        'viaje': widget.trip['id'],
      });
      final dir = await getTemporaryDirectory();
      final f = File('${dir.path}/${result['nombre']}');
      await f.writeAsString(result['archivo']);
      await Share.shareXFiles([
        XFile(f.path),
      ], text: 'Manifiesto interno. No acredita transmisión oficial al MTC.');
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Embarque'),
          actions: [
            IconButton(onPressed: export, icon: const Icon(Icons.ios_share)),
            IconButton(onPressed: load, icon: const Icon(Icons.refresh)),
          ],
        ),
        body: busy
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    widget.trip['ruta'],
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const Text(
                    'Croquis por asientos importados. La distribución física requiere la configuración real del bus.',
                  ),
                  TextField(
                    decoration: const InputDecoration(
                      labelText: 'Buscar asiento, nombre o documento',
                      prefixIcon: Icon(Icons.search),
                    ),
                    onChanged: (v) => setState(() => search = v.toLowerCase()),
                  ),
                  if (error.isNotEmpty) Text(error),
                  for (final floor in [1, 2]) ...[
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      child: Text(
                        'Piso $floor',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final p in passengers.where(
                          (p) =>
                              p['piso'] == floor &&
                              '${p['asiento']} ${p['nombre']} ${p['documento']}'
                                  .toLowerCase()
                                  .contains(search),
                        ))
                          SizedBox(
                            width: 92,
                            child: FilledButton.tonal(
                              onPressed: () => verify(p),
                              style: FilledButton.styleFrom(
                                backgroundColor: p['estado'] == 'EMBARCADO'
                                    ? Colors.green.shade100
                                    : p['estado'] == 'NO_PRESENTADO'
                                        ? Colors.red.shade100
                                        : null,
                                padding: const EdgeInsets.all(10),
                              ),
                              child: Column(
                                children: [
                                  const Icon(Icons.event_seat),
                                  Text('${p['asiento']}'),
                                  Text(
                                    p['estado'],
                                    style: const TextStyle(fontSize: 9),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ],
                  if (passengers.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(20),
                      child: Text(
                          'Ventas todavía no cargó la lista de pasajeros.'),
                    ),
                ],
              ),
      );
}
