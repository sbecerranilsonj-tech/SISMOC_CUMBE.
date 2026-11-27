# Fase 1 seguridad — correcciones de código Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar nueve hallazgos de seguridad de la Fase 1 sin tocar secretos, bases de datos, migraciones ni historial Git.

**Architecture:** Correcciones locales enDjango (A = web, B = escritorio) y pruebas de regresión por corrección. Cada tarea termina con suite verde; si falla, se revierte esa tarea.

**Tech Stack:** Django 5 + Ninja, Flutter/Dart, pytest-equivalente (`manage.py test`), `flutter test`.

**Spec:** `C:/Users/USUARIO/AppData/Local/Temp/opencode/diseno-fase1-seguridad.md`

## Global Constraints

- No modificar `.env`, `docker-compose.yml`, `compose.yaml`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, CORS, webview ni `dump_data.json`.
- No ejecutar migraciones ni escribir en la base real.
- No hacer `git push`.
- Mantener los contratos HTTP existentes (`/api/asistencia/marcar`, `/movil/api/<accion>/`, `/asistencia/huellero/agente/*`) salvo la eliminación explícita de parámetros inseguros.
- Gerente General conserva modo solo lectura.
- `HUELLERO_AGENTES` es la única fuente de agentes autorizados.

## Review Focus

- `next` externo debe caer al inicio: prueba en A y B.
- `ip`/`puerto` en la API del huellero deben ignorarse: prueba con parámetros hostiles.
- El token del agente no debe aparecer en ninguna respuesta HTTP: prueba en `agente_estado_web`.
- Consultar `inicio` en B no debe cambiar `usuario.rol`: prueba con ADMINISTRATIVO de área VENTAS.
- `is_staff` no debe poder editar `is_superuser` en `/admin`: prueba con cliente Django.
- Subida > límite o extensión inválida debe rechazarse antes de parsear: prueba con archivo falso.
- Errores 500 no deben contener `str(e)`: prueba con excepción forzada.
- Mensajes de error no deben incluir DNI ni ID biométrico: prueba de contenido.
- Crear usuario con clave corta debe fallar: prueba con `validate_password`.

---

### Task 1: Redirect abierto en login

**Files:** Modify `A/core/views.py:28-65`, `B/backend/core/views.py:21-69`; Test `A/core/test_credenciales.py`, `B/backend/core/test_credenciales.py`.

- [ ] **Step 1:** Escribir prueba: POST con `next=https://ejemploexterno.invalid` debe terminar en `dashboard`.
- [ ] **Step 2:** Ejecutarla y confirmar que falla.
- [ ] **Step 3:** Validar `next` con `url_has_allowed_host_and_scheme`; si falla, `redirect('dashboard')`.
- [ ] **Step 4:** Ejecutar la prueba y la suite de credenciales en A y B; deben pasar.
- [ ] **Step 5:** No commitear (el usuario decidirá commit/push).

### Task 2: SSRF en sincronización del huellero

**Files:** Modify `A/asistencia/api.py:137-145`, `B/backend/asistencia/api.py:137-145`; Test `A/asistencia/test_huellero_agente.py`.

- [ ] **Step 1:** Prueba: POST con `ip=10.0.0.1&puerto=22` no debe llamar a `socket.create_connection` con esos valores.
- [ ] **Step 2:** Confirmar falla.
- [ ] **Step 3:** Quitar parámetros `ip`/`puerto` del endpoint; usar `ZKTecoLiveClient()` sin argumentos.
- [ ] **Step 4:** Ejecutar prueba y suite de huellero; pasar.
- [ ] **Step 5:** Sin commit.

### Task 3: Token del agente y `agente_id`

**Files:** Modify `A/asistencia/services/zkteco_live.py:47-53`, `A/asistencia/views_huellero_agente.py:35-45,55-60,102-109,123-186,200-214`; Test `A/asistencia/test_huellero_agente.py`.

- [ ] **Step 1:** Prueba: `agente_estado_web` no devuelve `"token"`; `X-Agente-Id` no autorizado devuelve 403; token inválido con `compare_digest` devuelve 401.
- [ ] **Step 2:** Confirmar falla.
- [ ] **Step 3:** No devolver el token; comparar con `hmac.compare_digest`; validar `agente_id` contra `HUELLERO_AGENTES`.
- [ ] **Step 4:** Suite de huellero en verde.
- [ ] **Step 5:** Sin commit.

### Task 4: Auto-elevación de rol en escritorio

**Files:** Modify `B/backend/movil/funciones.py:16-21`, `B/backend/movil/views.py:91-92`; Test `B/backend/core/test_gerente_solo_consulta.py` o nuevo `B/backend/movil/test_funciones.py`.

- [ ] **Step 1:** Prueba: perfil ADMINISTRATIVO de área VENTAS consulta `inicio` y su `rol` permanece ADMINISTRATIVO.
- [ ] **Step 2:** Confirmar falla.
- [ ] **Step 3:** Convertir `sincronizar_funcion()` en no-op y quitar la llamada que escribe.
- [ ] **Step 4:** Suite de escritorio en verde.
- [ ] **Step 5:** Sin commit.

### Task 5: Escalada en `/admin` del escritorio

**Files:** Modify `B/backend/core/admin.py:58-70`; Test `B/backend/core/test_gerente_solo_consulta.py`.

- [ ] **Step 1:** Prueba: usuario `is_staff=True, is_superuser=False` no puede guardar `is_superuser=True`.
- [ ] **Step 2:** Confirmar falla.
- [ ] **Step 3:** Sobrescribir `has_change_permission`/`get_readonly_fields` para ocultar `is_superuser`, `groups`, `user_permissions`, `rol` a no superusers.
- [ ] **Step 4:** Suite en verde.
- [ ] **Step 5:** Sin commit.

### Task 6: Subida de archivos

**Files:** Modify `A/asistencia/views.py:753-766`, `A/asistencia/api.py:111-134`, `A/movil/gestion.py:85`, `A/conductores/views.py:67`; Test nuevo `A/asistencia/test_subidas_seguras.py`.

- [ ] **Step 1:** Prueba: archivo >10 MB y archivo con extensión falsa se rechazan antes de parsear.
- [ ] **Step 2:** Confirmar falla.
- [ ] **Step 3:** Helper `validar_archivo_subido()` con límite y magic bytes; usarlo en las cuatro entradas.
- [ ] **Step 4:** Suite en verde.
- [ ] **Step 5:** Sin commit.

### Task 7: Errores y logs sin PII

**Files:** Modify `A/asistencia/api.py:133-134`, `A/core/api.py:169,172`, `A/movil/_inspeccionar_marcas.py:5,11`, `A/herramientas/agente_huellero/agente.py:188-189`, `B/backend/core/api.py:169`, `B/desktop/launcher.py:47-50`; Test `A/config/test_notificaciones.py`.

- [ ] **Step 1:** Prueba: respuesta de error no contiene `"Traceback"` ni DNI de prueba.
- [ ] **Step 2:** Confirmar falla.
- [ ] **Step 3:** Mensaje genérico + `logger.exception()`; eliminar `print` de inspección; quitar DNI de mensajes.
- [ ] **Step 4:** Suite en verde.
- [ ] **Step 5:** Sin commit.

### Task 8: Contraseñas en creación de usuarios

**Files:** Modify `A/core/api.py:68-77,162-191`, `A/core/schemas.py:63,81,94`; Test `A/core/test_credenciales.py`.

- [ ] **Step 1:** Prueba: `new_password="abc123"` se rechaza con mensaje de validación.
- [ ] **Step 2:** Confirmar falla.
- [ ] **Step 3:** Llamar `validate_password` antes de `set_password`; conservar respuesta 400/422 existente.
- [ ] **Step 4:** Suite en verde.
- [ ] **Step 5:** Sin commit.

### Task 9: Verificación final y informe

- [ ] **Step 1:** Ejecutar A: `manage.py test core.test_credenciales core.test_gerente_solo_consulta config.test_notificaciones asistencia.test_exportacion_excel conductores.test_historial_archivos asistencia.test_huellero_agente --settings=config.test_settings --noinput`.
- [ ] **Step 2:** Ejecutar B: `manage.py test core.test_credenciales core.test_gerente_solo_consulta --settings=config.test_settings --noinput`.
- [ ] **Step 3:** Ejecutar `flutter test`.
- [ ] **Step 4:** Ejecutar `manage.py check` en A y B.
- [ ] **Step 5:** Escribir informe Markdown «antes → cambio → evidencia» y plan de Fase 2.
