# Fase 2 configuración Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar defaults inseguros y exponer solo lo necesario en web y escritorio, generando claves nuevas sin mostrarlas.

**Architecture:** Cambios de configuración y arranque; ninguna migración ni dato de negocio. Las claves nuevas se escriben en `.env` desde un script temporal con `secrets.token_urlsafe`.

**Tech Stack:** Django 5, Docker Compose, Waitress, pywebview.

**Spec:** `C:/Users/USUARIO/AppData/Local/Temp/opencode/diseno-fase2-configuracion.md`

## Global Constraints
- No modificar base de datos, migraciones ni datos de negocio.
- No mostrar valores de secretos en consola, chat ni archivos del proyecto; solo en `.env` local.
- No hacer `git push`.
- Mantener el arranque local funcional: `manage.py check` y login manual después de cada cambio de arranque.
- Las pruebas deben seguir pasando con `config.test_settings`.

## Review Focus
- `DEBUG` no debe quedar True por defecto en despliegue; hosts sin comodín; CORS no abierto.
- Cambiar `SECRET_KEY` cierra sesiones: avisar al usuario y verificar login.
- Compose no debe publicar 5432 ni 5051.
- Webview no debe descargar ni navegar fuera de loopback.
- Manifiesto de transferencia debe rechazarse si fue modificado.

---

### Task 1: Generar e inyectar claves nuevas
- [ ] **Step 1:** Script que lea `.env` y `.env.escritorio`, conserve las demás claves y escriba `SECRET_KEY`, `JWT_SIGNING_KEY` y `SISMOC_DESKTOP_SECRET` con valores aleatorios nuevos; no imprimir valores.
- [ ] **Step 2:** Verificar que los archivos siguen teniendo las mismas claves y que los valores son distintos de los anteriores (comparar hashes, no valores).
- [ ] **Step 3:** Avisar en el informe que las sesiones activas se invalidan.

### Task 2: Settings de web y escritorio
- [ ] **Step 1:** Prueba de que `config.settings` falla si falta `SECRET_KEY`/`JWT_SIGNING_KEY` en modo despliegue (test aislado con `override_settings` o lectura del módulo).
- [ ] **Step 2:** Ejecutar y confirmar fallo.
- [ ] **Step 3:** Requerir claves por entorno sin fallback inseguro; `DEBUG` por defecto False; `ALLOWED_HOSTS` explícito; CORS restringido fuera de desarrollo. Aplicar en A y B.
- [ ] **Step 4:** `manage.py check` y suites de credenciales en A y B.

### Task 3: Compose y arranque
- [ ] **Step 1:** Revisar `docker-compose.yml` y `compose.yaml` con `docker compose config`.
- [ ] **Step 2:** Sustituir secretos literales por `${VAR}`; quitar publicación de 5432/5051; 서비스 web con gunicorn; B con `runserver 127.0.0.1`.
- [ ] **Step 3:** Validar con `docker compose config` en ambos proyectos.

### Task 4: Webview y clave local
- [ ] **Step 1:** Prueba simple de que `launcher.py` no contiene `ALLOW_DOWNLOADS=True` ni `private_mode=False`.
- [ ] **Step 2:** Aplicar allowlist, descargas cerradas, enlaces externos al navegador y modo privado.
- [ ] **Step 3:** ACL de `.secret_key` al crearla y excluirla de `transfer_data.py`.

### Task 5: Manifiesto firmado
- [ ] **Step 1:** Prueba: alterar un archivo del paquete sin recalcular la firma debe fallar la verificación.
- [ ] **Step 2:** Implementar HMAC con clave local y verificación antes de extraer; respaldos antiguos requieren flag explícito.

### Task 6: Límite de intentos de login
- [ ] **Step 1:** Prueba: 6 intentos fallidos devuelven 429 y el quinto correcto también bloquea hasta expirar.
- [ ] **Step 2:** Implementar contador en caché por IP+identificador en `core/views.py` y `core/api.py` de A y B, con mensaje único.

### Task 7: Verificación y reinicio
- [ ] **Step 1:** `manage.py check`, suites amplias, Flutter.
- [ ] **Step 2:** Reiniciar contenedores y verificar login manual.
- [ ] **Step 3:** Informe Markdown de la Fase 2.
