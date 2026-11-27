import 'dart:convert';

import 'dart:io';



import 'package:flutter/material.dart';

import 'package:file_picker/file_picker.dart';

import 'package:geolocator/geolocator.dart';

import 'package:path_provider/path_provider.dart';

import 'package:share_plus/share_plus.dart';

import 'package:uuid/uuid.dart';



import 'api.dart';
import 'attendance_day_details.dart';
import 'sales_trips.dart';
import 'worker_dialogs.dart';

import 'activation_dialog.dart';

import 'pantalla_error.dart';
import 'abordaje.dart';

import 'password_field.dart';

String approvalLabel(Map jornada) {
  if (jornada['revision_contable'] == 'APROBADO' ||
      jornada['verificado_contabilidad'] == true) return 'Aprobado';
  if (jornada['revision_contable'] == 'OBSERVADO' ||
      jornada['estado_revision'] == 'OBSERVADO') return 'Observado';
  return 'Pendiente de aprobación';
}

String accountingHours(dynamic value) {
  final number = double.tryParse('$value');
  if (number == null || !number.isFinite) return '—';
  return number.toStringAsFixed(2).replaceAll('.', ',');
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  ErrorWidget.builder = (details) =>
      PantallaError(onRestart: () => runApp(const SismocApp()));
  runApp(const SismocApp());
}



class SismocApp extends StatelessWidget {

  const SismocApp({super.key});

  @override

  Widget build(BuildContext context) => MaterialApp(

        debugShowCheckedModeBanner: false,

        builder: (contexto, child) => MediaQuery(
          data: MediaQuery.of(contexto).copyWith(alwaysUse24HourFormat: true),
          child: child ?? const SizedBox.shrink(),
        ),

        title: 'El Cumbe',

        theme: ThemeData(

          useMaterial3: true,

          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xfff26522),
            primary: const Color(0xffef681f),
            onPrimary: Colors.white,
            surface: Colors.white,
            onSurface: const Color(0xff243431),
          ),
          appBarTheme: const AppBarTheme(
            elevation: 0,
            scrolledUnderElevation: 0,
            titleTextStyle: TextStyle(fontSize: 20,
                fontWeight: FontWeight.w700, color: Color(0xff34433e)),
          ),
          dialogTheme: DialogThemeData(
            backgroundColor: Colors.white,
            surfaceTintColor: Colors.transparent,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          ),
          filledButtonTheme: FilledButtonThemeData(
            style: FilledButton.styleFrom(
              minimumSize: const Size(48, 48),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
          ),
          scaffoldBackgroundColor: const Color(0xfff5f6fa),
          cardTheme: CardThemeData(
            color: Colors.white,
            surfaceTintColor: Colors.transparent,
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
              side: const BorderSide(color: Color(0xffe2eae7)),
            ),
          ),
          navigationBarTheme: NavigationBarThemeData(
            iconTheme: WidgetStateProperty.resolveWith((states) =>
                IconThemeData(color: states.contains(WidgetState.selected)
                    ? const Color(0xfff26522) : const Color(0xff75808b))),
            labelTextStyle: WidgetStateProperty.resolveWith((states) =>
                TextStyle(fontSize: 12,
                    color: states.contains(WidgetState.selected)
                        ? const Color(0xfff26522) : const Color(0xff75808b))),
          ),
          inputDecorationTheme: InputDecorationTheme(

            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),

            enabledBorder: OutlineInputBorder(

              borderRadius: BorderRadius.circular(10),

              borderSide: const BorderSide(color: Color(0xff9e9e9e)),

            ),

            focusedBorder: OutlineInputBorder(

              borderRadius: BorderRadius.circular(10),

              borderSide: const BorderSide(color: Color(0xfff26522), width: 1.6),

            ),

            labelStyle: const TextStyle(color: Color(0xff6f6f6f)),

            floatingLabelStyle: const TextStyle(color: Color(0xff6f6f6f)),

            contentPadding:

                const EdgeInsets.symmetric(horizontal: 14, vertical: 16),

          ),

        ),

        home: const Shell(),

      );

}



class Shell extends StatefulWidget {
  final SismocApi? api;
  const Shell({super.key, this.api});
  @override

  State<Shell> createState() => _ShellState();

}



class _ShellState extends State<Shell> {

  late final api = widget.api ?? SismocApi();
  final password = TextEditingController(), server = TextEditingController();

  bool loading = true, busy = false, offline = false;
  String offlineError = '';
  DateTime? attendanceMonth;
  DateTime? routeMonth;
  DateTime? historyMonth;
  int tripGroup = 0; // Hoy, Próximos, Historial.
  Map<String, dynamic>? routeData;
  bool routesLoading = false;
  int routesRequest = 0;
  Map<String, dynamic>? selectedAttendance;
  final Map<int, Map<String, dynamic>> dailyAttendance = {};
  final Set<int> loadingDays = {};
  final Map<int, String> dailyErrors = {};
  final Set<String> seenApprovals = {};
  bool attendanceLoading = false;
  int attendanceRequest = 0;
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
    final savedApprovals = await api.storage.read(
        key: 'avisos_vistos_${api.base}_${api.data['perfil']?['codigo'] ?? ''}');
    if (savedApprovals != null) {
      seenApprovals.addAll((jsonDecode(savedApprovals) as List).cast<String>());
    }
    server.text = api.base;

    if (api.token.isNotEmpty) {

      try {

        await api.refresh();

      } catch (e) {
        offline = true;
        offlineError = e is ApiError
            ? e.message
            : 'No se pudo contactar ${api.base}. Revise la dirección y la red.';
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
      if (driver && tab == 2) {
        await loadRoutesMonth(routeMonth ?? DateTime.now());
      }
      dailyAttendance.clear();
      dailyErrors.clear();
      if (attendanceMonth != null &&
          monthKey(attendanceMonth!) == monthKey(DateTime.now())) {
        selectedAttendance = {
          'resumen': api.data['resumen'],
          'marcaciones': api.data['marcaciones'],
          'jornadas': api.data['jornadas'],
        };
      }
    } catch (e) {
      offline = true;
      offlineError = e is ApiError
          ? e.message
          : 'No se pudo contactar ${api.base}. Revise la dirección y la red.';
      rethrow;
    }
    offline = false;
    offlineError = '';
    if (mounted) setState(() {});
  }

  String monthKey(DateTime month) =>
      '${month.year}-${month.month.toString().padLeft(2, '0')}';

  Future<DateTime?> pickAttendanceMonth({bool forRoutes = false}) {
    final now = DateTime.now();
    final first = DateTime(now.year - 5, now.month);
    final last = forRoutes ? DateTime(now.year + 1, now.month) : now;
    final initial = (forRoutes ? routeMonth : attendanceMonth) ?? now;
    var year = initial.year;
    const names = [
      'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
      'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
    ];
    return showDialog<DateTime>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Seleccione mes y año'),
          content: SizedBox(
            width: 320,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DropdownButton<int>(
                  value: year,
                  isExpanded: true,
                  items: [
                    for (var y = last.year; y >= first.year; y--)
                      DropdownMenuItem(value: y, child: Text('$y')),
                  ],
                  onChanged: (value) {
                    if (value != null) update(() => year = value);
                  },
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (var i = 1; i <= 12; i++)
                      SizedBox(
                        width: 76,
                        child: OutlinedButton(
                          onPressed: DateTime(year, i).isBefore(first) ||
                                  DateTime(year, i).isAfter(last)
                              ? null
                              : () => Navigator.pop(
                                  dialogContext, DateTime(year, i)),
                          child: Text(names[i - 1]),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> chooseAttendanceMonth() async {
    final month = await pickAttendanceMonth();
    if (month == null || !mounted) return;
    final id = ++attendanceRequest;
    setState(() {
      attendanceMonth = month;
      selectedAttendance = null;
      dailyAttendance.clear();
      dailyErrors.clear();
      attendanceLoading = true;
    });
    try {
      final result = await api.attendanceMonth(monthKey(month));
      if (mounted && id == attendanceRequest) {
        setState(() => selectedAttendance = result);
      }
    } catch (e) {
      if (mounted && id == attendanceRequest) {
        message(e is ApiError ? e.message : 'No se pudo consultar el período.');
      }
    } finally {
      if (mounted && id == attendanceRequest) {
        setState(() => attendanceLoading = false);
      }
    }
  }

  Future<void> loadRoutesMonth(DateTime month) async {
    final id = ++routesRequest;
    if (mounted) setState(() {
      routeMonth = DateTime(month.year, month.month);
      routeData = null;
      routesLoading = true;
    });
    try {
      final result = await api.routesMonth(monthKey(month));
      if (mounted && id == routesRequest) {
        setState(() => routeData = result);
      }
    } catch (e) {
      if (mounted && id == routesRequest) {
        message(e is ApiError ? e.message : 'No se pudieron consultar los viajes.');
      }
    } finally {
      if (mounted && id == routesRequest) {
        setState(() => routesLoading = false);
      }
    }
  }

  Future<void> chooseRouteMonth() async {
    final month = await pickAttendanceMonth(forRoutes: true);
    if (month != null && mounted) {
      historyMonth = month;
      await loadRoutesMonth(month);
    }
  }

  void selectTripGroup(int group) {
    if (tripGroup == group) return;
    setState(() => tripGroup = group);
    final month = group == 2 ? (historyMonth ?? DateTime.now()) : DateTime.now();
    if (routeMonth == null || monthKey(routeMonth!) != monthKey(month)) {
      loadRoutesMonth(month);
    }
  }

  Future<void> loadAttendanceDay(int id) async {
    if (dailyAttendance.containsKey(id) || loadingDays.contains(id)) return;
    setState(() {
      loadingDays.add(id);
      dailyErrors.remove(id);
    });
    try {
      final result = await api.attendanceDay(id);
      if (mounted && loadingDays.contains(id)) {
        setState(() => dailyAttendance[id] = result);
      }
    } catch (e) {
      if (mounted && loadingDays.contains(id)) {
        setState(() => dailyErrors[id] =
            e is ApiError ? e.message : 'No se pudo consultar el control diario.');
      }
    } finally {
      if (mounted) setState(() => loadingDays.remove(id));
    }
  }

  String approvalKey(dynamic item) =>
      '${item['id']}:${item['fecha_revision'] ?? ''}';

  int get unreadNotices =>
      ((api.data['avisos'] ?? []) as List).where((n) => n['leido'] != true).length +
      ((api.data['avisos_validacion'] ?? []) as List)
          .where((n) => !seenApprovals.contains(approvalKey(n))).length;

  Future<void> showNotices() async {
    final approvals = (api.data['avisos_validacion'] ?? []) as List;
    final notices = (api.data['avisos'] ?? []) as List;
    await showDialog<void>(
      context: context,
      builder: (context) => NoticesDialog(
        notices: notices.whereType<Map>().toList(),
        approvals: approvals.whereType<Map>().toList(),
      ),
    );
    if (!mounted) return;
    seenApprovals.addAll(approvals.map(approvalKey));
    await api.storage.write(
      key: 'avisos_vistos_${api.base}_${api.data['perfil']?['codigo'] ?? ''}',
      value: jsonEncode(seenApprovals.toList()),
    );
    final pending = notices.where((n) => n['leido'] != true).map((n) => n['id']).toList();
    if (pending.isNotEmpty) {
      try {
        await api.post('avisos', {'ids': pending});
        await api.refresh();
      } catch (_) {
        // Se mantienen pendientes en el servidor para el próximo intento.
      }
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



  static const Color accent = Color(0xfff26522);

  static const Color ink = Color(0xff222222);

  static const Color muted = Color(0xff6f6f6f);



  Future<void> _login() => run(() async {

        api.base = server.text.trim().replaceAll(RegExp(r'/$'), '');

        final remembered =

            await api.storage.read(key: 'worker_code_${api.base}') ?? '';

        if (remembered.isEmpty) {

          message('Primero activa este celular con tu código temporal.');

          return;

        }

        await api.login(remembered, password.text, '');

        password.clear();

        offline = false;

      });



  Future<void> _changeServer(String value) async {

    server.text = value;

    api.base = value;

    api.workerCode =

        await api.storage.read(key: 'worker_code_$value') ?? '';

    await api.storage.write(key: 'base', value: value);

    if (mounted) setState(() {});

  }



  Future<void> _openServerDialog() async {

    final url = TextEditingController(text: server.text);

    String? error;

    final value = await showDialog<String>(

      context: context,

      builder: (ctx) => StatefulBuilder(

        builder: (ctx, setDialogState) => AlertDialog(

          shape:

              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),

          title: const Text('Servidor de SISMOC'),

          content: Column(

            mainAxisSize: MainAxisSize.min,

            crossAxisAlignment: CrossAxisAlignment.stretch,

            children: [

              const Text(

                'Escriba la dirección del servidor al que se conectará este celular.',

                style: TextStyle(fontSize: 13, color: muted),

              ),

              const SizedBox(height: 14),

              TextField(

                controller: url,

                keyboardType: TextInputType.url,

                autocorrect: false,

                decoration: const InputDecoration(

                  labelText: 'URL del servidor',

                  hintText: 'http://127.0.0.1:8000',

                ),

              ),

              if (error != null)

                Padding(

                  padding: const EdgeInsets.only(top: 10),

                  child: Text(

                    error!,

                    style:

                        const TextStyle(color: Color(0xffd32f2f), fontSize: 12),

                  ),

                ),

            ],

          ),

          actions: [

            TextButton(

              onPressed: () => Navigator.pop(ctx),

              child: const Text('Cancelar'),

            ),

            FilledButton(

              onPressed: () {

                final value = url.text.trim().replaceAll(RegExp(r'/+$'), '');

                final uri = Uri.tryParse(value);

                if (uri == null ||

                    !['http', 'https'].contains(uri.scheme) ||

                    uri.host.isEmpty) {

                  setDialogState(() => error =

                      'Use una dirección completa, por ejemplo http://127.0.0.1:8000.');

                  return;

                }

                Navigator.pop(ctx, value);

              },

              child: const Text('Guardar'),

            ),

          ],

        ),

      ),

    );

    url.dispose();

    if (value != null) {

      await _changeServer(value);

      if (mounted) message('Servidor actualizado.');

    }

  }



  Widget _loginPage() {

    final hasAccount = api.workerCode.isNotEmpty;

    return Scaffold(

      backgroundColor: Colors.white,

      body: SafeArea(

        child: LayoutBuilder(

          builder: (context, constraints) => SingleChildScrollView(

            padding: const EdgeInsets.fromLTRB(26, 16, 26, 28),

            child: ConstrainedBox(

              constraints: BoxConstraints(

                minHeight: constraints.maxHeight > 44

                    ? constraints.maxHeight - 44

                    : 0,

              ),

              child: Center(

                child: ConstrainedBox(

                  constraints: const BoxConstraints(maxWidth: 420),

                  child: Column(

                    mainAxisSize: MainAxisSize.min,

                    crossAxisAlignment: CrossAxisAlignment.stretch,

                    children: [

                      Center(

                        child: Image.asset(

                          'assets/el-cumbe-marca.png',

                          height: 186,

                          fit: BoxFit.contain,

                        ),

                      ),

                      const SizedBox(height: 14),

                      const Text(

                        'Iniciar Sesión',

                        style: TextStyle(

                          fontSize: 30,

                          fontWeight: FontWeight.w700,

                          color: ink,

                          letterSpacing: .2,

                        ),

                      ),

                      const SizedBox(height: 22),

                      TextFormField(

                        key: ValueKey('codigo-${api.workerCode}'),

                        initialValue: api.workerCode,

                        readOnly: true,

                        enableInteractiveSelection: true,

                        style: const TextStyle(fontSize: 15, color: ink),

                        decoration: InputDecoration(

                          labelText: 'Código de trabajador',

                          hintText: 'Sin cuenta activada',

                          floatingLabelBehavior: FloatingLabelBehavior.always,

                          prefixIcon:

                              const Icon(Icons.person_outline, size: 20),

                          suffixIcon: hasAccount

                              ? const Padding(

                                  padding: EdgeInsets.only(right: 16),

                                  child: Text(

                                    '*',

                                    style: TextStyle(

                                      color: Color(0xffe53935),

                                      fontSize: 20,

                                      fontWeight: FontWeight.w700,

                                    ),

                                  ),

                                )

                              : null,

                          suffixIconConstraints: const BoxConstraints(

                            minWidth: 30,

                            minHeight: 20,

                          ),

                        ),

                      ),

                      const SizedBox(height: 16),

                      PasswordField(

                        controller: password,

                        label: 'Contraseña',

                        enabled: hasAccount && !busy,

                        prefixIcon: Icons.lock_outline,

                        textInputAction: TextInputAction.done,

                        onSubmitted: hasAccount ? (_) => _login() : null,

                      ),

                      const SizedBox(height: 24),

                      SizedBox(

                        height: 54,

                        child: FilledButton(

                          onPressed: busy

                              ? null

                              : (hasAccount ? _login : activateAccount),

                          style: FilledButton.styleFrom(

                            backgroundColor: accent,

                            foregroundColor: Colors.white,

                            disabledBackgroundColor: const Color(0xffffb27a),

                            shape: RoundedRectangleBorder(

                              borderRadius: BorderRadius.circular(9),

                            ),

                            textStyle: const TextStyle(

                              fontSize: 15,

                              fontWeight: FontWeight.w700,

                              letterSpacing: 1.4,

                            ),

                          ),

                          child: busy

                              ? const SizedBox(

                                  width: 22,

                                  height: 22,

                                  child: CircularProgressIndicator(

                                    strokeWidth: 2.2,

                                    color: Colors.white,

                                  ),

                                )

                              : Text(

                                  hasAccount

                                      ? 'INGRESAR'

                                      : 'ACTIVAR MI CUENTA',

                                ),

                        ),

                      ),

                      const SizedBox(height: 16),

                      Wrap(

                        alignment: WrapAlignment.center,

                        crossAxisAlignment: WrapCrossAlignment.center,

                        children: [

                          Text(

                            hasAccount

                                ? '¿Otro trabajador?'

                                : '¿No tienes cuenta?',

                            style: const TextStyle(

                              fontSize: 13.5,

                              color: muted,

                            ),

                          ),

                          TextButton(

                            onPressed: busy ? null : activateAccount,

                            style: TextButton.styleFrom(

                              foregroundColor: accent,

                              padding:

                                  const EdgeInsets.symmetric(horizontal: 6),

                              minimumSize: const Size(0, 36),

                              tapTargetSize: MaterialTapTargetSize.shrinkWrap,

                            ),

                            child: Text(

                              hasAccount

                                  ? 'Activar otra cuenta'

                                  : 'Activar mi cuenta',

                              style: const TextStyle(

                                fontSize: 13.5,

                                fontWeight: FontWeight.w700,

                              ),

                            ),

                          ),

                        ],

                      ),

                      const SizedBox(height: 12),

                      SizedBox(

                        height: 50,

                        child: OutlinedButton(

                          onPressed: busy ? null : _openServerDialog,

                          style: OutlinedButton.styleFrom(

                            foregroundColor: accent,

                            side: const BorderSide(color: accent, width: 1.1),

                            shape: RoundedRectangleBorder(

                              borderRadius: BorderRadius.circular(9),

                            ),

                            textStyle: const TextStyle(

                              fontSize: 12.5,

                              fontWeight: FontWeight.w700,

                              letterSpacing: .7,

                            ),

                          ),

                          child: const Text(

                            'CONFIGURAR SERVIDOR',

                            textAlign: TextAlign.center,

                          ),

                        ),

                      ),

                      const SizedBox(height: 12),

                      Text(

                        'Servidor: ${server.text}',

                        textAlign: TextAlign.center,

                        style: const TextStyle(

                          fontSize: 11.5,

                          color: Color(0xff8a8a8a),

                        ),

                      ),

                    ],

                  ),

                ),

              ),

            ),

          ),

        ),

      ),

    );

  }



  Widget box(String title, List<Widget> children) => Card(

        margin: const EdgeInsets.only(bottom: 16),

        child: Padding(

          padding: const EdgeInsets.all(18),

          child: Column(

            crossAxisAlignment: CrossAxisAlignment.stretch,

            children: [

              Row(children: [
                Container(
                  width: 3, height: 18,
                  decoration: BoxDecoration(color: accent,
                      borderRadius: BorderRadius.circular(2)),
                ),
                const SizedBox(width: 10),
                Expanded(child: Text(title, style: const TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700))),
              ]),
              const SizedBox(height: 14),

              ...children,

            ],

          ),

        ),

      );

  Widget button(String text, VoidCallback action, {IconData? icon}) => Padding(

        padding: const EdgeInsets.symmetric(vertical: 6),
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

    if (api.token.isEmpty || api.data['perfil'] == null) return _loginPage();

    final labels = [

      'Inicio',

      'Asistencia',

      role == 'OPERADOR_EMBARQUE' ? 'Embarque' : sales ? 'Programación y ventas' : 'Viajes',
      'Solicitudes',
      'Mi cuenta',
      'Embarque',
    ];
    final sections = [0, if (!driver) 1, if (canTrips) 2, if (driver) 5, 3, 4];
    final currentTab = sections.contains(tab) ? tab : 0;

    return Scaffold(

      appBar: AppBar(

        centerTitle: true,
        backgroundColor: const Color(0xfff6fcfa),
        foregroundColor: const Color(0xff704c3b),
        title: Text(driver && currentTab == 2 ? 'Mis viajes' : currentTab == 4 ? 'Perfil' : labels[currentTab]),
        actions: [
          IconButton(
            onPressed: showNotices,
            tooltip: 'Avisos',
            icon: Badge(
              isLabelVisible: unreadNotices > 0,
              label: Text('${unreadNotices > 99 ? '99+' : unreadNotices}'),
              child: const Icon(Icons.notifications_outlined),
            ),
          ),
          IconButton(
            onPressed: busy ? null : () => run(refresh),

            icon: const Icon(Icons.sync),

          ),

        ],

      ),

      bottomNavigationBar: NavigationBar(
        backgroundColor: Colors.white,
        indicatorColor: const Color(0xffffeadc),
        selectedIndex: sections.indexOf(currentTab),

        onDestinationSelected: (v) {
          final next = sections[v];
          setState(() => tab = next);
          if (driver && next == 2 && routeData == null && !routesLoading) {
            loadRoutesMonth(routeMonth ?? DateTime.now());
          }
        },
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
               label: role == 'OPERADOR_EMBARQUE' ? 'Embarque' : driver ? 'Viajes' : sales ? 'Ventas' : 'Viajes',
            ),
          if (driver)
            const NavigationDestination(
              icon: Icon(Icons.airline_seat_recline_normal),
              label: 'Embarque',
            ),
          NavigationDestination(

            icon: Icon(Icons.event_note),

            label: 'Solicitudes',

          ),

          NavigationDestination(

            icon: Icon(Icons.person_outline),

            label: 'Perfil',
          ),

        ],

      ),

      backgroundColor: const Color(0xfff6fcfa),
      body: Column(
        children: [

          if (busy) const LinearProgressIndicator(),

          if (offline)

            MaterialBanner(
              content: Text(
                'Sin conexión · datos guardados. ${offlineError.isEmpty ? 'Algunas acciones requieren conexión.' : offlineError}',
              ),

              actions: [SizedBox()],

            ),

          Expanded(

            child: (currentTab == 5 && driver) ||
                    (currentTab == 2 && role == 'OPERADOR_EMBARQUE')
                ? PanelAbordaje(api: api, embedded: true, onCroquis: abrirCroquis)
                : RefreshIndicator(

              onRefresh: () => run(refresh),

              child: ListView(

                padding: const EdgeInsets.all(16),

                children: [

                  if (currentTab == 0) ...home(),

                  if (currentTab == 1) ...attendance(),

                   if (currentTab == 2 && canTrips) ...trips(),
                   if (currentTab == 5 && driver) ...driverBoarding(),
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



  void openDriverTrips() {
    setState(() => tab = 2);
    if (routeData == null && !routesLoading) {
      loadRoutesMonth(routeMonth ?? DateTime.now());
    }
  }

  Widget driverMetric(String label, int value) => Container(
        constraints: const BoxConstraints(minWidth: 92),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: const Color(0xff19263f),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('$value', style: const TextStyle(color: Colors.white,
              fontSize: 22, fontWeight: FontWeight.w700)),
          Text(label, style: const TextStyle(color: Color(0xffb5c5db),
              fontSize: 10, fontWeight: FontWeight.w700)),
        ]),
      );

  List<Widget> home() {
    final p = api.data['perfil'];
    final now = DateTime.now();
    final today = '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    final realAssigned = ((api.data['viajes'] ?? []) as List)
        .where((v) => v['asignado'] == true).toList();
    final assigned = <dynamic>[
      ...realAssigned,
    ]..sort((a, b) {
        final aDate = '${a['fecha']}';
        final bDate = '${b['fecha']}';
        if (aDate == today && bDate != today) return -1;
        if (bDate == today && aDate != today) return 1;
        return aDate.compareTo(bDate);
      });
    final pendientes = assigned.where((v) =>
        !['FINALIZADO', 'CANCELADO', 'NO_PRESENTADO']
            .contains('${v['estado']}')).toList();
    final todayAssigned = pendientes;
    final hoyPendientes =
        pendientes.where((v) => '${v['fecha']}' == today).length;
    final todayTrips = hoyPendientes;
    final activeTrips = assigned.where((v) => v['estado'] == 'EN_CURSO').length;
    final completedTrips = assigned.where((v) => v['estado'] == 'FINALIZADO').length;
    return [
      const Text('EL CUMBE · MI ESPACIO',
          style: TextStyle(fontSize: 11, letterSpacing: 1.5,
              fontWeight: FontWeight.w700, color: Color(0xffb56535))),
      const SizedBox(height: 8),
      Text('Hola, ${p['nombre']}',
          style: const TextStyle(fontSize: 23, height: 1.25,
              fontWeight: FontWeight.w700, color: Color(0xff34433e))),
      const SizedBox(height: 16),
      if (!driver) ...[
        box('Acciones de marcación de hoy', [
          const Text(
            'Ubícate en tu zona autorizada. El sistema comprobará la precisión del GPS. La hora válida se toma del servidor.',
          ),
          const SizedBox(height: 10),
          if (api.data['ausencia_hoy'] == true)
            const Text(
                'Tienes permiso o vacaciones aprobados para hoy. No corresponde marcar asistencia.'),
          if (api.data['comision_actual'] == true)
            const Text('Comisión vigente: puedes marcar sin ubicación.'),
          if (api.data['ausencia_hoy'] != true) dailyActions(),
        ]),
        const SizedBox(height: 16),
        box('Mi horario', [
          for (final h in (api.data['horarios'] ?? []) as List)
            ListTile(title: Text(h['fecha']), subtitle: Text(h['turno'])),
          if ((api.data['horarios'] ?? []).isEmpty)
            const Text('Sin programación publicada. Solicita revisar tu horario.'),
        ]),
        const SizedBox(height: 16),
      ],
      if (driver) ...[
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: const Color(0xff101a30),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('PANEL CONDUCTOR', style: TextStyle(
                color: Color(0xffff8a4b), fontWeight: FontWeight.w700,
                letterSpacing: 1, fontSize: 11)),
            const SizedBox(height: 8),
            Text('Tus viajes de hoy · ${now.day}/${now.month}/${now.year}',
                style: const TextStyle(color: Colors.white, fontSize: 19,
                    fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            const Text('Consulta tus viajes y reporta novedades desde aquí.',
                style: TextStyle(color: Color(0xffb5c5db))),
            const SizedBox(height: 20),
            Wrap(spacing: 8, runSpacing: 8, children: [
              driverMetric('HOY', todayTrips),
              driverMetric('EN RUTA', activeTrips),
              driverMetric('FINALIZADOS', completedTrips),
            ]),
          ]),
        ),
        const SizedBox(height: 16),
        box('Tus rutas asignadas', [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xff263348),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(children: [
              const Icon(Icons.directions_bus, size: 42, color: Colors.white),
              const SizedBox(height: 10),
              Text(todayAssigned.isEmpty
                      ? 'Sin asignaciones pendientes.'
                      : hoyPendientes == todayAssigned.length
                          ? '${todayAssigned.length} ${todayAssigned.length == 1 ? 'viaje' : 'viajes'} de hoy'
                          : '${todayAssigned.length} ${todayAssigned.length == 1 ? 'viaje pendiente' : 'viajes pendientes'}',
                  style: const TextStyle(color: Colors.white,
                      fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              if (todayAssigned.isEmpty)
                const Text('No tienes rutas pendientes. Las nuevas asignaciones aparecerán aquí.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Color(0xffccd6e5))),
              for (final trip in todayAssigned)
                Material(
                  color: Colors.transparent,
                  child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${trip['ruta']}',
                      style: TextStyle(color: trip['validacion_pendiente'] == true
                          ? (trip['descanso_insuficiente'] == true
                              ? const Color(0xffffb4b4) : const Color(0xfffcd9a4))
                          : Colors.white,
                          fontWeight: FontWeight.w700)),
                  subtitle: Text(trip['validacion_pendiente'] == true
                      ? (trip['descanso_insuficiente'] == true
                          ? 'Aún no cumples las 8 horas de descanso'
                          : 'En espera de confirmar llegada')
                      : '${trip['hora']} · ${trip['bus'] ?? 'Bus por confirmar'}',
                      style: TextStyle(color: trip['validacion_pendiente'] == true
                          ? (trip['descanso_insuficiente'] == true
                              ? const Color(0xffffc7c7) : const Color(0xfffde3bd))
                          : const Color(0xffccd6e5))),
                  trailing: Icon(Icons.chevron_right,
                      color: trip['validacion_pendiente'] == true
                          ? (trip['descanso_insuficiente'] == true
                              ? const Color(0xffffb4b4) : const Color(0xfffcd9a4))
                          : Colors.white),
                  onTap: () => showDriverTrip(trip),
                  ),
                ),
            ]),
          ),
          if (canTrips)
            TextButton.icon(
              onPressed: openDriverTrips,
              icon: const Icon(Icons.arrow_forward),
              label: const Text('Consultar rutas asignadas'),
            ),
        ]),
      ],
      if (unreadNotices > 0 && !driver)
        box('Avisos', [
          for (final notice in ((api.data['avisos'] ?? []) as List)
              .where((n) => n['leido'] != true).take(2))
            Text('• ${notice['texto']}'),
          for (final notice in ((api.data['avisos_validacion'] ?? []) as List)
              .where((n) => !seenApprovals.contains(approvalKey(n))).take(2))
            Text('• Jornada ${notice['fecha']} validada por Contabilidad'),
          if (unreadNotices > 4)
            Text('Y ${unreadNotices - 4} avisos más.'),
          TextButton.icon(
            onPressed: showNotices,
            icon: const Icon(Icons.notifications_outlined),
            label: const Text('Ver avisos'),
          ),
        ]),
      if (api.pending.any(
          (item) => item['account'] == api.data['perfil']['codigo']))
        pendingSync(),
    ];
  }

  Widget pendingSync() {
    final items = api.pending.where(
        (item) => item['account'] == api.data['perfil']['codigo']).toList();
    return box('Envíos pendientes · ${items.length}', [
      const Text('Se guardaron sin conexión. Envíalos cuando tengas internet para que SISMOC los registre.'),
      button('Enviar pendientes', () => run(refresh), icon: Icons.sync),
      for (final item in items)
        ListTile(
          title: Text('${item['action']}'),
          subtitle: Text(item['error'].toString().isEmpty
              ? 'Por enviar' : '${item['error']}'),
          trailing: IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Descartar intento pendiente',
            onPressed: () async {
              if (await confirm(
                'Descartar intento',
                'Esta acción solo elimina este envío pendiente del teléfono. No modifica registros que ya recibió SISMOC.',
              )) {
                await run(() async {
                  api.pending.remove(item);
                  await api.persistQueue();
                  if (mounted) setState(() {});
                });
              }
            },
          ),
        ),
    ]);
  }


  Widget dailyActions() {
    const actions = [
      ('ENTRADA', 'Entrada', 'Comenzar jornada', Icons.login),
      ('SALIDA_REFRIGERIO', 'Refrigerio', 'Iniciar descanso', Icons.coffee_outlined),
      ('RETORNO_REFRIGERIO', 'Retorno', 'Volver del refrigerio', Icons.undo),
      ('SALIDA', 'Salida', 'Finalizar jornada', Icons.logout),
    ];
    return LayoutBuilder(builder: (context, constraints) {
      final scale = MediaQuery.textScalerOf(context).scale(1);
      final columns = constraints.maxWidth < 260 || scale > 1.3 ? 1 : 2;
      final width = (constraints.maxWidth - (columns - 1) * 12) / columns;
      return Padding(
        padding: const EdgeInsets.only(top: 12),
        child: Wrap(spacing: 12, runSpacing: 12, children: [
          for (final action in actions)
            SizedBox(
              width: width,
              child: OutlinedButton(
                onPressed: busy ? null : () async {
                  final accepted = await confirm(
                    'Confirmar marcación',
                    '¿Registrar ${action.$2.toLowerCase()}? Se aplicarán las validaciones de ubicación y hora habituales.',
                  );
                  if (accepted && mounted) await run(() => mark(action.$1));
                },
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xff263d35),
                  backgroundColor: Colors.white,
                  padding: const EdgeInsets.all(14),
                  alignment: Alignment.centerLeft,
                  side: const BorderSide(color: Color(0xffdfe8e2)),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(9),
                      decoration: BoxDecoration(
                        color: const Color(0xfffff0e4),
                        borderRadius: BorderRadius.circular(11),
                      ),
                      child: Icon(action.$4, size: 23, color: accent),
                    ),
                    const SizedBox(height: 12),
                    Text(action.$2, style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 5),
                    Text(action.$3, style: const TextStyle(
                        fontSize: 12, color: Color(0xff61746b))),
                  ],
                ),
              ),
            ),
        ]),
      );
    });
  }

  Widget metric(String label, dynamic value) => Container(
      width: 126,
      constraints: const BoxConstraints(minHeight: 90),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xfff3f7f5),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,

        children: [

          SizedBox(
            width: double.infinity,
            height: 32,
            child: FittedBox(
              alignment: Alignment.centerLeft,
              fit: BoxFit.scaleDown,
              child: Text('${value ?? 0}',
                  maxLines: 1,
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
            ),
          ),
          const SizedBox(height: 4),
          Text(label, style: const TextStyle(fontSize: 12, color: Color(0xff65756e))),
        ],

      ));
  Widget periodSummary() {
    final r = (selectedAttendance ?? api.data)['resumen'] ?? {};
    return box('Mi asistencia del período', [

      Text('Desde ${r['desde'] ?? ''} · Horas decimales',
          style: const TextStyle(fontSize: 12, color: Color(0xff65756e))),
      const SizedBox(height: 12),

      Wrap(spacing: 24, runSpacing: 16, children: [

        metric('Jornadas', r['jornadas']),

        metric('Horas trabajadas', accountingHours(r['horas_trabajadas'])),
        metric('Extras 25 %', accountingHours(r['horas_extras_25'])),
        metric('Extras 35 %', accountingHours(r['horas_extras_35'])),
        metric('Horas nocturnas', accountingHours(r['horas_nocturnas'])),
      ]),
      const SizedBox(height: 12),
      Text('${r['aprobadas'] ?? 0}/${r['jornadas'] ?? 0} aprobadas · '
          '${r['pendientes'] ?? 0} pendientes · ${r['observadas'] ?? 0} observadas',
          style: const TextStyle(fontSize: 12, color: Color(0xff65756e))),
    ]);

  }
  Widget accountingDay(Map j) {
    final id = j['id'] as int;
    final day = dailyAttendance[id];
    final status = day?['revision_contable'] == 'APROBADO'
        ? 'Aprobado' : approvalLabel(j);
    final approved = status == 'Aprobado';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Material(
      color: const Color(0xfff3f7f5),
      borderRadius: BorderRadius.circular(12),
      child: ExpansionTile(
        onExpansionChanged: (expanded) {
          if (expanded) loadAttendanceDay(id);
        },
        tilePadding: const EdgeInsets.symmetric(horizontal: 12),
        childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        title: Text('${j['fecha']}', style: const TextStyle(
            fontSize: 14, fontWeight: FontWeight.w700)),
        subtitle: Text(status, style: TextStyle(
            fontSize: 12,
            color: approved ? const Color(0xff24744f) : const Color(0xffa45b25))),
        children: [
          if (loadingDays.contains(id))
            const Padding(padding: EdgeInsets.all(12),
                child: CircularProgressIndicator())
          else if (dailyErrors.containsKey(id))
            TextButton(
              onPressed: () => loadAttendanceDay(id),
              child: Text('${dailyErrors[id]} · Reintentar'),
            )
          else if (day != null)
            AttendanceDayDetails(day: day),
        ],
      )),
    );
  }
  List<Widget> attendance() => [
        if (!driver) ...[
          box('Consultar período', [
            TextButton.icon(
              onPressed: chooseAttendanceMonth,
              icon: const Icon(Icons.calendar_month),
              label: Text(attendanceMonth == null
                  ? 'Mes actual · Elegir mes y año'
                  : '${monthKey(attendanceMonth!)} · Cambiar mes'),
            ),
          ]),
          if (attendanceLoading)
            const Center(child: CircularProgressIndicator())
          else if (attendanceMonth != null && selectedAttendance == null)
            box('Asistencia del período', [
              const Text('No se pudo cargar este mes. Elija el período para reintentar.'),
            ])
          else
            periodSummary(),
        ],
        if (!attendanceLoading && (attendanceMonth == null || selectedAttendance != null))
        box('Horas y aprobación', [
          const Text(

            'Consulta las jornadas calculadas por SISMOC. Un registro recibido no significa que ya haya sido aprobado para pago.',

          ),

          for (final j in ((selectedAttendance ?? api.data)['jornadas'] ?? []) as List)
            accountingDay(j as Map),
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



  bool routeIsToday(dynamic trip) {
    final now = DateTime.now();
    final localToday =
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    return trip['fecha'] == (routeData?['hoy'] ?? localToday);
  }

  bool routeIsPast(dynamic trip) =>
      routeData != null &&
      '${trip['fecha']}'.compareTo('${routeData!['hoy']}') < 0;

  String routeStatus(dynamic trip) {
    if (trip['llegada_pendiente'] == true) return 'LLEGADA PENDIENTE';
    if (!driver || !routeIsPast(trip)) return '${trip['estado']}';
    if (trip['estado_salida'] == 'REALIZADO') return 'REALIZADO';
    if (trip['reporte_validado'] == true) return 'REPORTE VALIDADO';
    return 'HISTÓRICO';
  }

  Widget driverTripCard(dynamic trip) {
    final sinDescanso = trip['descanso_insuficiente'] == true;
    final pendiente = trip['validacion_pendiente'] == true;
    final aviso = sinDescanso
        ? 'Aún no cumples las 8 horas de descanso'
        : pendiente
            ? 'En espera de confirmar llegada'
            : '';
    final color = sinDescanso
        ? const Color(0xffdc2626)
        : pendiente
            ? const Color(0xfff59e0b)
            : const Color(0xffef681f);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => showDriverTrip(trip),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 17),
          child: Row(children: [
            Container(
              width: 3,
              height: 40,
              decoration: BoxDecoration(color: color,
                  borderRadius: BorderRadius.circular(3)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('${trip['ruta']}',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700,
                          color: sinDescanso ? const Color(0xffb91c1c) : null)),
                  const SizedBox(height: 5),
                  Text('${trip['fecha']} · ${trip['hora']}',
                      style: const TextStyle(color: Color(0xff64726d), fontSize: 13)),
                  if (pendiente || sinDescanso) ...[
                    const SizedBox(height: 6),
                    Text(aviso,
                        style: TextStyle(color: sinDescanso
                            ? const Color(0xffb91c1c) : const Color(0xffb45309),
                            fontSize: 12.5, fontWeight: FontWeight.w700)),
                  ],
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: color),
          ]),
        ),
      ),
    );
  }


  List<Widget> groupedDriverTrips() {
    if (routesLoading || routeData == null) return [];
    final today = '${routeData!['hoy']}';
    final trips = <dynamic>[
      ...((routeData!['viajes'] ?? []) as List),
    ]
        .where((v) {
          final date = '${v['fecha']}';
          if (tripGroup == 0) return date == today;
          if (tripGroup == 1) return date.compareTo(today) > 0;
          return date.compareTo(today) < 0
              || (date == today && v['estado'] == 'FINALIZADO');
        })
        .toList()
      ..sort((a, b) {
        final dateOrder = '${a['fecha']}'.compareTo('${b['fecha']}');
        if (dateOrder != 0) return tripGroup == 2 ? -dateOrder : dateOrder;
        return '${a['hora']}'.compareTo('${b['hora']}');
      });
    if (trips.isEmpty) {
      return [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Text(tripGroup == 0
              ? 'No tienes viajes para hoy.'
              : tripGroup == 1
                  ? 'No tienes próximos viajes este mes.'
                  : 'No hay viajes anteriores en este mes.'),
        ),
      ];
    }
    if (tripGroup == 2) {
      final weeks = <DateTime, List<dynamic>>{};
      for (final trip in trips) {
        final date = DateTime.tryParse('${trip['fecha']}');
        if (date == null) continue;
        final monday = date.subtract(Duration(days: date.weekday - 1));
        weeks.putIfAbsent(monday, () => []).add(trip);
      }
      return [
        for (final entry in weeks.entries)
          Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: ExpansionTile(
              key: ValueKey('semana-${monthKey(routeMonth ?? DateTime.now())}-${entry.key.toIso8601String()}'),
              title: Text(
                'Semana ${entry.key.day.toString().padLeft(2, '0')}/${entry.key.month.toString().padLeft(2, '0')}'
                ' – ${entry.key.add(const Duration(days: 6)).day.toString().padLeft(2, '0')}/${entry.key.add(const Duration(days: 6)).month.toString().padLeft(2, '0')}',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              subtitle: Text('${entry.value.length} ${entry.value.length == 1 ? 'viaje' : 'viajes'}'),
              childrenPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              children: [for (final trip in entry.value) driverTripCard(trip)],
            ),
          ),
      ];
    }
    final result = <Widget>[];
    String? lastDate;
    for (final trip in trips) {
      final date = '${trip['fecha']}';
      if (date != lastDate) {
        result.add(Padding(
          padding: const EdgeInsets.only(top: 12, bottom: 8),
          child: Text(date == today ? 'Hoy · $date' : date,
              style: const TextStyle(
                  fontSize: 15, fontWeight: FontWeight.w700)),
        ));
        lastDate = date;
      }
      result.add(driverTripCard(trip));
    }
    return result;
  }

  String iniciales(dynamic valor) {
    final palabras = '$valor'.trim().split(RegExp(r'\s+'));
    if (palabras.isEmpty) return '—';
    return palabras.take(2).map((p) => p.isNotEmpty ? p[0] : '').join().toUpperCase();
  }

  Widget _lineaTiempo(String etiqueta, String hora, Color color) => Row(
    mainAxisAlignment: MainAxisAlignment.spaceBetween,
    children: [
      Row(children: [
        Container(width: 10, height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 10),
        Text(etiqueta, style: const TextStyle(color: Color(0xff64726d), fontSize: 13)),
      ]),
      Text(hora, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
    ],
  );

  Widget _datoCompacto(String etiqueta, String valor) => Container(
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: Colors.white,
      border: Border.all(color: const Color(0xffe2e8f0)),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(etiqueta, style: const TextStyle(
          color: Color(0xff64726d), fontSize: 10, fontWeight: FontWeight.w700)),
      const SizedBox(height: 4),
      Text(valor, maxLines: 2, overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700,
            color: Color(0xff243431))),
    ]),
  );

  Widget _conductorFila(dynamic nombre, Color fondo, Color color) => Row(
    children: [
      Container(width: 26, height: 26,
        decoration: BoxDecoration(color: fondo, shape: BoxShape.circle),
        child: Center(child: Text(iniciales(nombre),
          style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)))),
      const SizedBox(width: 9),
      Expanded(child: Text('$nombre',
        style: const TextStyle(fontSize: 12, color: Color(0xff243431)))),
    ],
  );

  Future<void> showDriverTrip(dynamic trip) {
    const navy = Color(0xff1d293e);
    const orange = Color(0xfff47732);
    final ahora = DateTime.now().toLocal();
    final inicioViaje = DateTime.tryParse(trip['salida_real'] ?? '')
        ?? DateTime.tryParse('${trip['fecha']}T${trip['hora']}:00');
    final llegadaTardia = inicioViaje == null
        || ahora.difference(inicioViaje) >= const Duration(hours: 9)
        || ahora.year != inicioViaje.year
        || ahora.month != inicioViaje.month
        || ahora.day != inicioViaje.day;
    String displayTime(dynamic value) {
      if (value == null) return 'No registrada';
      final parsed = value is DateTime
          ? value : DateTime.tryParse('$value');
      if (parsed == null) return 'No registrada';
      final time = parsed.toLocal();
      return '${time.day.toString().padLeft(2, '0')}/'
          '${time.month.toString().padLeft(2, '0')}/${time.year} '
          '${time.hour.toString().padLeft(2, '0')}:'
          '${time.minute.toString().padLeft(2, '0')}';
    }
    String horaCorta(dynamic value) {
      if (value == null) return 'No registrada';
      final parsed = value is DateTime ? value : DateTime.tryParse('$value');
      if (parsed == null) return 'No registrada';
      final local = parsed.toLocal();
      return '${local.hour.toString().padLeft(2, '0')}:'
          '${local.minute.toString().padLeft(2, '0')}';
    }
    final acciones = <Widget>[];
    if (trip['asignado'] == true && routeIsToday(trip)) {
      acciones.add(Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text('${trip['disponibilidad']?['mensaje'] ?? ''}',
            style: const TextStyle(color: Color(0xff64726d), fontSize: 13)),
      ));
      if (trip['estado'] == 'PROGRAMADO' && trip['confirmado'] != true)
        acciones.add(button('Confirmar mi salida',
            () => confirmEvent(trip, 'INICIAR')));
      if (trip['estado'] == 'PROGRAMADO' && trip['confirmado'] == true)
        acciones.add(const Text('Salida registrada. Viaje en curso para ambos conductores.',
            style: TextStyle(color: Color(0xff15803d), fontSize: 13)));
      if (trip['estado'] == 'EN_CURSO') {
        if (trip['conduce'] == true)
          acciones.add(const Text('Viaje en curso · conductor al mando.',
              style: TextStyle(color: Color(0xff64726d), fontSize: 13)));
        if (trip['confirmado'] != true)
          acciones.add(button('Registrar mi llegada',
              () => confirmEvent(trip, 'LLEGADA')));
      }
      if (trip['estado'] == 'FINALIZADO')
        acciones.add(const Text(
          'Descanso iniciado automáticamente al registrar la llegada.',
          style: TextStyle(color: Color(0xff15803d), fontSize: 13)));
    }
    if (trip['llegada_pendiente'] == true && trip['asignado'] == true)
      acciones.add(button(
        llegadaTardia ? 'Regularizar llegada olvidada' : 'Finalizar viaje',
        () => regularizarLlegada(trip),
        icon: Icons.check_circle_outline));

    return showDialog<void>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (dialogContext, updateDialog) => Dialog.fullscreen(
            child: Scaffold(
              backgroundColor: const Color(0xfff4f6f9),
              appBar: AppBar(
                title: const Text('Detalle del Viaje'),
                leading: IconButton(
                  tooltip: 'Cerrar',
                  onPressed: () => Navigator.pop(dialogContext),
                  icon: const Icon(Icons.arrow_back),
                ),
              ),
              body: SafeArea(
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Align(
                      alignment: Alignment.centerRight,
                      child: Chip(label: Text(routeStatus(trip))),
                    ),
                    const SizedBox(height: 8),
                    Card(
                      clipBehavior: Clip.antiAlias,
                      child: Column(children: [
                        Container(height: 4, color: orange),
                        Padding(
                          padding: const EdgeInsets.all(16),
                          child: Row(children: [
                            Container(
                              width: 38, height: 38,
                              decoration: const BoxDecoration(
                                color: Color(0xffffefe5),
                                borderRadius: BorderRadius.all(Radius.circular(11)),
                              ),
                              child: const Icon(Icons.directions_bus,
                                  color: orange, size: 22),
                            ),
                            const SizedBox(width: 12),
                            Expanded(child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('${trip['ruta']}',
                                    style: const TextStyle(fontSize: 18,
                                        fontWeight: FontWeight.w800, color: navy)),
                                Text('Bus: ${trip['bus'] ?? 'No informado'}',
                                    style: const TextStyle(
                                        color: Color(0xff64726d), fontSize: 13)),
                              ],
                            )),
                            Column(crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text('${trip['fecha']}',
                                    style: const TextStyle(fontSize: 12,
                                        color: Color(0xff243431))),
                                Text('${trip['hora']}',
                                    style: const TextStyle(fontSize: 14,
                                        fontWeight: FontWeight.w700, color: orange)),
                              ],
                            ),
                          ]),
                        ),
                      ]),
                    ),
                    if (acciones.isNotEmpty) ...[
                      Card(child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: acciones),
                      )),
                      const SizedBox(height: 12),
                    ],
                    Card(child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Línea de tiempo',
                              style: TextStyle(fontSize: 15,
                                  fontWeight: FontWeight.w700, color: navy)),
                          const SizedBox(height: 12),
                          Container(
                            margin: const EdgeInsets.only(left: 6),
                            padding: const EdgeInsets.only(left: 14),
                            decoration: const BoxDecoration(
                              border: Border(left: BorderSide(
                                  color: Color(0xffffd9c2), width: 2)),
                            ),
                            child: Column(children: [
                              _lineaTiempo('Inicio', horaCorta(trip['salida_real']), orange),
                              const SizedBox(height: 16),
                              _lineaTiempo('Llegada', horaCorta(trip['llegada_real']),
                                  const Color(0xff16a34a)),
                            ]),
                          ),
                          const SizedBox(height: 10),
                          const Text(
                            'Horas informativas · el trayecto se valida en la web.',
                            style: TextStyle(fontSize: 11, color: Color(0xff8a8a8a))),
                        ],
                      ),
                    )),
                    const SizedBox(height: 12),
                    Row(children: [
                      Expanded(child: _datoCompacto('PASAJEROS', '${trip['pasajeros'] ?? 0}')),
                      const SizedBox(width: 8),
                      Expanded(child: _datoCompacto('PUNTOS DE RECOJO',
                          ((trip['puntos'] as List?) ?? []).isEmpty
                              ? 'No informados' : (trip['puntos'] as List).join(', '))),
                    ]),
                    if (trip['distancia_km'] != null || trip['duracion_estimada'] != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Wrap(spacing: 8, children: [
                          if (trip['distancia_km'] != null)
                            Chip(label: Text('${trip['distancia_km']} km')),
                          if (trip['duracion_estimada'] != null)
                            Chip(label: Text('Tiempo: ${trip['duracion_estimada']}')),
                        ]),
                      ),
                    const SizedBox(height: 12),
                    Card(child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Conductores',
                              style: TextStyle(fontSize: 15,
                                  fontWeight: FontWeight.w700, color: navy)),
                          const SizedBox(height: 10),
                          _conductorFila(trip['conductor_1'], const Color(0xffffefe5), orange),
                          const SizedBox(height: 8),
                          _conductorFila(trip['conductor_2'], const Color(0xffe8f1ff),
                              const Color(0xff2563eb)),
                        ],
                      ),
                    )),
                    if (routeIsPast(trip))
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: const Color(0xfffff8e6),
                            border: Border.all(color: const Color(0xfffcd9a4)),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: const Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('SOLO CONSULTA · VIAJE HISTÓRICO',
                                  style: TextStyle(fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                      color: Color(0xffb45309))),
                              SizedBox(height: 3),
                              Text('Un reporte validado no confirma un viaje realizado.',
                                  style: TextStyle(fontSize: 12,
                                      color: Color(0xff8a6a3a))),
                            ],
                          ),
                        ),
                      ),
                    for (final incidencia in (trip['incidencias'] as List?) ?? [])
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Card(child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${incidencia['tipo']} · ${incidencia['estado']}',
                                  style: const TextStyle(fontWeight: FontWeight.w700,
                                      color: Color(0xffb91c1c), fontSize: 13)),
                              const SizedBox(height: 4),
                              Text('${incidencia['descripcion']}',
                                  style: const TextStyle(
                                      color: Color(0xff64726d), fontSize: 13)),
                            ],
                          ),
                        )),
                      ),
                    const SizedBox(height: 16),
                    if (trip['asignado'] == true &&
                        trip['embarque'] == true && routeIsToday(trip))
                      button('Ver croquis y pasajeros', () => Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => ManifiestoEmbarque(
                            api: api, viajeId: trip['id'], onCroquis: abrirCroquis)),
                      ), icon: Icons.airline_seat_recline_normal),
                    if (routeIsToday(trip))
                      button('Reportar incidencia o gasto', () => incident(trip),
                          icon: Icons.report_outlined),
                    const SizedBox(height: 8),
                    Center(child: TextButton(
                      onPressed: () => Navigator.pop(dialogContext),
                      child: const Text('Cerrar',
                          style: TextStyle(fontWeight: FontWeight.w700)),
                    )),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
  }

  List<Widget> driverBoarding() {
    final now = DateTime.now();
    final today = routeData?['hoy'] ??
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    final assigned = ((api.data['viajes'] ?? []) as List).where((v) =>
        v['asignado'] == true &&
        '${v['fecha']}'.compareTo('$today') >= 0 &&
        v['estado'] != 'CANCELADO').toList();
    return [
      box('Embarque de mi bus', [
        const Text('Solo viajes reales asignados a tu bus. '
            'Los viajes de prueba y de otros conductores no aparecen aquí.'),
        if (assigned.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('No tienes viajes asignados para embarque.'),
          ),
        for (final v in assigned)
          button(
            '${v['fecha']} · ${v['hora']} · ${v['ruta']} · Bus ${v['bus']}',
            () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => ManifiestoEmbarque(
                  api: api, viajeId: v['id'], onCroquis: abrirCroquis),
              ),
            ),
            icon: Icons.airline_seat_recline_normal,
          ),
      ]),
    ];
  }

  Future<void> abrirCroquis(DatosAbordaje viaje) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) =>
      Boarding(api: api, trip: viaje)));
  }

  Future<void> viewSalesTrip(Map trip) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: Colors.white,
      builder: (sheet) => FractionallySizedBox(
        heightFactor: .85,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 12, 12),
            child: Row(children: [
              const Expanded(child: Text('Detalle del viaje',
                  style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700,
                      color: Color(0xff172b45)))),
              TextButton(onPressed: () => Navigator.pop(sheet),
                  child: const Text('Cerrar')),
            ]),
          ),
          const Divider(height: 1),
          Expanded(child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${trip['ruta']}', style: const TextStyle(
                  color: Color(0xff172b45), fontSize: 22, fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Text(salesDate(trip)),
              Text('Bus: ${trip['bus']} · ${salesStatus(trip)}'),
              const SizedBox(height: 20),
              const Text('Conductores', style: TextStyle(fontWeight: FontWeight.w700)),
              for (final key in ['conductor_1', 'conductor_2'])
                Text('${trip[key] ?? ''}'.trim().isEmpty
                    ? 'Sin asignar' : '${trip[key]}'),
              const SizedBox(height: 16),
              Text('Pasajeros reportados: ${trip['pasajeros'] ?? 'Sin información'}'),
              if ((trip['puntos'] as List? ?? []).isNotEmpty)
                Text('Puntos de embarque: ${(trip['puntos'] as List).join(', ')}'),
              if (trip['embarque'] == true) ...[
                const SizedBox(height: 12),
                button('Ver croquis y pasajeros', () {
                  Navigator.pop(sheet);
                  Navigator.push(context, MaterialPageRoute(builder: (_) =>
                      ManifiestoEmbarque(
                          api: api, viajeId: trip['id'], onCroquis: abrirCroquis)));
                }, icon: Icons.airline_seat_recline_normal),
              ],
              if ((trip['incidencias'] as List? ?? []).isNotEmpty) ...[
                const SizedBox(height: 20),
                const Text('Incidencias y gastos',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                for (final item in trip['incidencias'] as List)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('${item['tipo']} · ${item['estado']}'),
                    subtitle: Text('${item['descripcion']}'),
                    trailing: role == 'GERENTE_GENERAL' ? null : const Icon(Icons.chevron_right),
                    onTap: role == 'GERENTE_GENERAL' ? null : () {
                      Navigator.pop(sheet);
                      run(() => send('resolver_incidencia', {
                        'id': item['id'], 'estado': 'RESUELTO',
                      }));
                    },
                  ),
              ],
            ]),
          )),
        ]),
      ),
    );
  }

  List<Widget> trips() => [
        if (sales)
          SalesTripsView(
            key: const ValueKey('sales-trips'),
            trips: ((api.data['viajes'] ?? []) as List).whereType<Map>().toList(),
            busy: busy,
            canManage: role != 'GERENTE_GENERAL',
            onImport: () => run(importTrips),
            onBoarding: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) =>
                    PanelAbordaje(api: api, onCroquis: abrirCroquis))),
            onView: viewSalesTrip,
            onAssign: (trip) => assign(trip),
            onAssignBoarding: (trip) => assignBoarding(trip),
            onPassengers: (trip) => run(() => importPassengers(trip)),
            onIncident: (trip) => incident(trip),
          ),
        if (driver) ...[
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: SizedBox(
              width: double.infinity,
              child: SegmentedButton<int>(
                segments: const [
                  ButtonSegment(value: 0, label: Text('Hoy')),
                  ButtonSegment(value: 1, label: Text('Próximos')),
                  ButtonSegment(value: 2, label: Text('Historial')),
                ],
                selected: {tripGroup},
                onSelectionChanged: (selection) =>
                    selectTripGroup(selection.first),
              ),
            ),
          ),
          if (tripGroup == 2)
            Card(
              margin: const EdgeInsets.only(bottom: 12),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                child: Row(children: [
                  Container(
                    width: 34, height: 34,
                    decoration: BoxDecoration(
                      color: const Color(0xffffefe5),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.calendar_month_outlined,
                        color: Color(0xfff26522), size: 18),
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('CONSULTAR VIAJES POR MES',
                          style: TextStyle(fontSize: 10, color: Color(0xff6f6f6f),
                              fontWeight: FontWeight.w700)),
                      Text(monthKey(historyMonth ?? DateTime.now()),
                          style: const TextStyle(fontSize: 14,
                              fontWeight: FontWeight.w700,
                              color: Color(0xff243431))),
                    ],
                  )),
                  IconButton(
                    onPressed: chooseRouteMonth,
                    tooltip: 'Cambiar mes',
                    icon: const Icon(Icons.calendar_month_outlined,
                        color: Color(0xfff26522)),
                  ),
                ]),
              ),
            ),
          if (routesLoading)
            const Center(child: CircularProgressIndicator())
          else if (routeData == null)
            box('Viajes del mes', [
              const Text('No se pudo cargar este mes. Elija el mes para reintentar.'),
            ])
          else
            box('Mi período · ${routeData!['mes']}', [
              Wrap(spacing: 12, runSpacing: 12, children: [
                metric('Trayectos del mes', routeData!['resumen']['trayectos_realizados']),
                metric('Vueltas', routeData!['resumen']['vueltas']),
                metric('Estimado', 'S/ ${routeData!['resumen']['estimado']}'),
              ]),
              const SizedBox(height: 12),
              Text('HORA ${routeData!['resumen']['HORA']} · '
                  'X ${routeData!['resumen']['X']} · XX ${routeData!['resumen']['XX']}'),
              const Text('Importes estimados por viajes finalizados. '
                  'La aprobación y el pago se revisan en SISMOC.'),
            ]),
          if (!routesLoading && routeData != null) ...groupedDriverTrips(),
        ],
        for (final v in driver || sales ? <dynamic>[] : (api.data['viajes'] ?? []) as List)
            box('${v['fecha']} · ${v['hora']}', [
            if (driver) ...[
              Align(
                alignment: Alignment.centerRight,
                child: Chip(
                   label: Text(routeStatus(v),
                      style: const TextStyle(fontSize: 11,
                          color: Color(0xff1684a0))),
                  backgroundColor: const Color(0xffedf6f7),
                  side: BorderSide.none,
                ),
              ),
              const Divider(),
              Row(children: [
                const Icon(Icons.calendar_month, color: Color(0xffffa21a), size: 20),
                const SizedBox(width: 8),
                Flexible(child: Text('${v['fecha']} · ${v['hora']}')),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                const Icon(Icons.directions_bus, color: Color(0xffffa21a), size: 20),
                const SizedBox(width: 8),
                Flexible(child: Text('Bus: ${v['bus']}')),
              ]),
              const SizedBox(height: 12),
            ],
            Text(v['ruta'], style: Theme.of(context).textTheme.titleLarge),

            Text('${v['bus']} · ${routeStatus(v)}'),
            Text('${v['conductor_1']}\n${v['conductor_2']}'),

            Text('Pasajeros reportados: ${v['pasajeros'] ?? 'No informado'}'),

            Text('Embarques: ${(v['puntos'] as List).join(', ')}'),

            const SizedBox(height: 8),

            if (driver && routeIsPast(v))
              const Text('Ruta de fecha pasada · solo consulta. '
                  'La validación del reporte no cambia el estado operativo del viaje.',
                  style: TextStyle(fontSize: 12, color: Color(0xff65756e))),
            if (v['asignado'] == true && (!driver || routeIsToday(v))) ...[
              Text(v['disponibilidad']['mensaje']),

              if (v['estado'] == 'PROGRAMADO' && v['confirmado'] != true)
                button('Confirmar mi salida', () => confirmEvent(v, 'INICIAR'))
              else if (v['estado'] == 'PROGRAMADO' && v['confirmado'] == true)
                const Text('Salida confirmada. Esperando al otro conductor.'),
              if (v['estado'] == 'EN_CURSO') ...[
                if (v['conduce'] == true)
                  const Text('Viaje en curso · conductor al mando.'),
                if (v['confirmado'] == true)
                  const Text('Llegada registrada por ti.')
                else
                  button('Registrar mi llegada', () => confirmEvent(v, 'LLEGADA')),
              ],

              if (v['estado'] == 'FINALIZADO')

                button(

                  'Terminé labores · iniciar descanso',

                  () => confirmEvent(v, 'DESCANSO'),

                ),

            ],

            if (v['embarque'] == true && (!driver || routeIsToday(v)))
              button(

                'Ver croquis y pasajeros',

                () => Navigator.push(

                  context,

                  MaterialPageRoute(

                    builder: (_) =>

                        ManifiestoEmbarque(api: api, viajeId: v['id'],
                          onCroquis: abrirCroquis),

                  ),

                ),

                icon: Icons.airline_seat_recline_normal,

              ),

            if (!driver || routeIsToday(v))
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

        if (!driver && !sales && ((api.data['viajes'] ?? []) as List).isEmpty)
          box(driver ? 'Mis viajes' : sales ? 'Programación y ventas' : 'Embarques', [
            Text(driver ? 'No hay viajes asignados para este período.'
                : sales ? 'No hay salidas publicadas para este período.'
                : 'No hay embarques autorizados para este período.'),
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

  Future<void> regularizarLlegada(dynamic v) async {
    final ahora = DateTime.now().toLocal();
    String dois(int n) => n.toString().padLeft(2, '0');
    final inicio = DateTime.tryParse(v['salida_real'] ?? '')
        ?? DateTime.tryParse('${v['fecha']}T${v['hora']}:00');
    final tardia = inicio == null
        || ahora.difference(inicio) >= const Duration(hours: 9)
        || ahora.year != inicio.year
        || ahora.month != inicio.month
        || ahora.day != inicio.day;
    final titulo = tardia ? 'Regularizar llegada' : 'Finalizar viaje';
    final fechaCtrl = TextEditingController(
        text: '${dois(ahora.day)}/${dois(ahora.month)}/${ahora.year}');
    final horaCtrl = TextEditingController(
        text: '${dois(ahora.hour)}:${dois(ahora.minute)}');
    final motivoCtrl = TextEditingController();
    final datos = await showDialog<Map<String, String>>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        titlePadding: const EdgeInsets.fromLTRB(24, 18, 24, 4),
        contentPadding: const EdgeInsets.fromLTRB(24, 4, 24, 8),
        title: Row(children: [
          Container(
            padding: const EdgeInsets.all(9),
            decoration: const BoxDecoration(
              color: Color(0xffffefe5), shape: BoxShape.circle),
            child: Icon(
              tardia ? Icons.history_toggle_off : Icons.check_circle_outline,
              color: const Color(0xfff26522), size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(titulo,
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700,
                  color: Color(0xff243431)))),
        ]),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text(
              tardia
                  ? 'Registra la hora real en que llegaste. Se guardará con auditoría para revisar el descanso posterior.'
                  : 'Confirma tu llegada al destino. Se registrará la hora del servidor para ambos conductores.',
              style: const TextStyle(color: Color(0xff6f6f6f), height: 1.35)),
            const SizedBox(height: 16),
            TextField(
              controller: fechaCtrl,
              readOnly: true,
              onTap: () async {
                final elegida = await showDatePicker(
                  context: ctx,
                  initialDate: ahora,
                  firstDate: DateTime(ahora.year - 1),
                  lastDate: ahora.add(const Duration(days: 1)),
                );
                if (elegida != null) fechaCtrl.text =
                    '${dois(elegida.day)}/${dois(elegida.month)}/${elegida.year}';
              },
              decoration: const InputDecoration(labelText: 'Fecha'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: horaCtrl,
              readOnly: true,
              onTap: () async {
                final elegida = await showTimePicker(
                  context: ctx,
                  initialTime: TimeOfDay.fromDateTime(ahora),
                  initialEntryMode: TimePickerEntryMode.input,
                  builder: (contexto, child) => MediaQuery(
                    data: MediaQuery.of(contexto).copyWith(
                        alwaysUse24HourFormat: true),
                    child: child!,
                  ),
                );
                if (elegida != null) horaCtrl.text =
                    '${dois(elegida.hour)}:${dois(elegida.minute)}';
              },
              decoration: const InputDecoration(labelText: 'Hora'),
            ),
            const SizedBox(height: 6),
            const Text('Sin zona horaria · hora local de Perú.',
                style: TextStyle(fontSize: 11, color: Color(0xff8a8a8a))),
            const SizedBox(height: 14),
            TextField(
              controller: motivoCtrl,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Motivo (opcional)',
                alignLabelWithHint: true,
              ),
            ),
          ]),
        ),
        actionsPadding: const EdgeInsets.fromLTRB(24, 0, 24, 14),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
          FilledButton.icon(
              onPressed: () => Navigator.pop(ctx, {
                    'llegada': '${fechaCtrl.text.trim()} ${horaCtrl.text.trim()}',
                    'motivo': motivoCtrl.text.trim(),
                  }),
              icon: const Icon(Icons.save_outlined, size: 18),
              label: Text(tardia ? 'Guardar' : 'Finalizar viaje')),
        ],
      ),
    );
    if (datos == null) return;
    final partes = RegExp(r'^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})$')
        .firstMatch(datos['llegada'] ?? '');
    if (partes == null) {
      message('Revise la fecha y la hora de llegada.');
      return;
    }
    final llegada = DateTime(
      int.parse(partes.group(3)!), int.parse(partes.group(2)!),
      int.parse(partes.group(1)!), int.parse(partes.group(4)!),
      int.parse(partes.group(5)!),
    );
    await run(() => send('regularizar_llegada', {
          'id': const Uuid().v4(),
          'viaje': v['id'],
          'llegada': llegada.toLocal().toIso8601String(),
          'motivo': datos['motivo'],
        }));
  }

  void confirmEvent(dynamic v, String type) async {

    if (await confirm(

      'Confirmar acción',

      type == 'DESCANSO'

          ? 'Confirmo que terminé mis labores y comienzo descanso fuera del bus.'

          : type == 'INICIAR'
              ? 'Confirmo que estoy a bordo y que el viaje inicia en ${v['ruta']}. Se registrará la hora del servidor y se notificará al otro conductor.'
              : type == 'LLEGADA'
                  ? 'Confirmo mi llegada en ${v['ruta']}. Se registrará la hora del servidor; el viaje cierra cuando el otro conductor confirme.'
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
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => NewRequestDialog(
        shifts: ((api.data['turnos'] ?? []) as List).whereType<Map>().toList(),
      ),
    );
    if (result != null) await run(() => send('solicitud', result));
  }



  List<Widget> account() => [
        const Center(
          child: CircleAvatar(
            radius: 52,
            backgroundColor: Color(0xffffa21a),
            child: Icon(Icons.person, size: 78, color: Colors.white),
          ),
        ),
        const SizedBox(height: 18),
        Text('${api.data['perfil']['nombre']}',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 23, fontWeight: FontWeight.bold,
                color: Color(0xff704c3b))),
        Text(driver ? 'Conductor' : role.replaceAll('_', ' '),
            textAlign: TextAlign.center),
        const SizedBox(height: 24),
        box('Información personal', [
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const CircleAvatar(
              backgroundColor: Color(0xfffff4e4),
              child: Icon(Icons.badge_outlined, color: Color(0xffffa21a)),
            ),
            title: const Text('Código de trabajador'),
            subtitle: Text('${api.data['perfil']['codigo']}'),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const CircleAvatar(
              backgroundColor: Color(0xfffff4e4),
              child: Icon(Icons.business_outlined, color: Color(0xffffa21a)),
            ),
            title: const Text('Área'),
            subtitle: Text('${api.data['perfil']['area'] ?? 'No informada'}'),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const CircleAvatar(
              backgroundColor: Color(0xfffff4e4),
              child: Icon(Icons.location_on_outlined, color: Color(0xffffa21a)),
            ),
            title: const Text('Sede'),
            subtitle: Text(
                '${api.data['perfil']['sede'] ?? ''}'.trim().isEmpty
                    ? 'Sin sede asignada' : '${api.data['perfil']['sede']}'),
          ),
          const Text(
            'Las modificaciones de ficha, dispositivo y permisos las realiza la administración.',

          ),

        ]),

        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: FilledButton.icon(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xffffebee),
              foregroundColor: const Color(0xffbf3a35),
              minimumSize: const Size.fromHeight(48),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: busy ? null : () => run(() async { await api.logout(); }),
            icon: const Icon(Icons.logout),
            label: const Text('CERRAR SESIÓN'),
          ),
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
