import 'dart:convert';
import 'dart:async';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';
import 'package:flutter/foundation.dart';

class ApiError implements Exception {
  final String message;
  final int status;
  ApiError(this.message, this.status);
  @override
  String toString() => message;
}

class SismocApi {
  final storage = const FlutterSecureStorage();
  String base = 'http://10.0.2.2:8000';
  String token = '';
  String device = '';
  String workerCode = '';
  Map<String, dynamic> data = {};
  List<Map<String, dynamic>> pending = [];
  Future<void> restore() async {
    base = await storage.read(key: 'base') ?? base;
    workerCode = await storage.read(key: 'worker_code_$base') ?? '';
    token = await storage.read(key: 'token') ?? '';
    device = await storage.read(key: 'device') ?? const Uuid().v4();
    await storage.write(key: 'device', value: device);
    final cache = await storage.read(key: 'cache');
    if (cache != null) data = Map<String, dynamic>.from(jsonDecode(cache));
    final queue = await storage.read(key: 'queue');
    if (queue != null)
      pending = (jsonDecode(queue) as List)
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
  }

  Future<Map<String, dynamic>> post(
    String action,
    Map<String, dynamic> body,
  ) async {
    final uri = Uri.parse('$base/movil/api/$action/');
    if (uri.scheme != 'https' && !kReleaseMode) {
      // HTTP únicamente en compilaciones de desarrollo, para la laptop local.
    } else if (uri.scheme != 'https') {
      throw ApiError('El servidor de producción debe usar HTTPS.', 400);
    }
    http.Response response;
    try {
      response = await http
          .post(
            uri,
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $token',
            },
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 30));
    } on TimeoutException {
      throw ApiError(
          'SISMOC no respondió en $base. Compruebe el servidor y la conexión USB o Wi-Fi.',
          0);
    } on http.ClientException {
      throw ApiError(
          'No se puede conectar a $base. Si usa USB, active adb reverse y use http://127.0.0.1:8000.',
          0);
    }
    Map<String, dynamic> result;
    try {
      result = Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)),
      );
    } catch (_) {
      throw ApiError(
        'El servidor devolvió una respuesta inválida (${response.statusCode}).',
        response.statusCode,
      );
    }
    if (result['ok'] != true)
      throw ApiError(
        result['error']?.toString() ?? 'Error del servidor.',
        response.statusCode,
      );
    return result;
  }

  Future<void> login(String code, String password, String activation) async {
    final result = await post(activation.isEmpty ? 'login' : 'activar', {
      'codigo': code,
      'password': password,
      'activacion': activation,
      'dispositivo': device,
    });
    token = result.remove('token') as String;
    await storage.write(key: 'base', value: base);
    await storage.write(key: 'token', value: token);
    workerCode = code;
    await storage.write(key: 'worker_code_$base', value: code);
    await save(result);
  }

  Future<Map<String, dynamic>> verifyActivation(String code) =>
      post('verificar_activacion', {'activacion': code, 'dispositivo': device});

  Future<void> finishActivation(
      String ticket, String password, String confirmation) async {
    final result = await post('establecer_password', {
      'ticket': ticket,
      'password': password,
      'confirmacion': confirmation,
      'dispositivo': device
    });
    workerCode = result['codigo'] as String;
    token = '';
    data = {};
    await storage.delete(key: 'token');
    await storage.delete(key: 'cache');
    await storage.write(key: 'base', value: base);
    await storage.write(key: 'worker_code_$base', value: workerCode);
  }

  Future<void> save(Map<String, dynamic> value) async {
    data = value;
    await storage.write(key: 'cache', value: jsonEncode(data));
  }

  Future<void> refresh() async => save(await post('inicio', {}));
  Future<void> queue(String action, Map<String, dynamic> body) async {
    pending.add({
      'action': action,
      'body': body,
      'account': data['perfil']['codigo'],
      'error': '',
    });
    await persistQueue();
  }

  Future<void> persistQueue() async =>
      storage.write(key: 'queue', value: jsonEncode(pending));
  Future<void> sync() async {
    for (final item in List<Map<String, dynamic>>.from(pending)) {
      if (item['account'] != data['perfil']?['codigo']) continue;
      try {
        await post(item['action'], Map<String, dynamic>.from(item['body']));
        pending.remove(item);
      } on ApiError catch (e) {
        item['error'] = e.message;
        if (e.status == 401) break;
      } catch (_) {
        break;
      }
    }
    await persistQueue();
  }

  Future<void> logout() async {
    try {
      await post('logout', {});
    } finally {
      token = '';
      data = {};
      final all = await storage.readAll();
      for (final key in all.keys.where(
        (key) =>
            key == 'token' || key == 'cache' || key.startsWith('passengers_'),
      )) {
        await storage.delete(key: key);
      }
    }
  }
}
