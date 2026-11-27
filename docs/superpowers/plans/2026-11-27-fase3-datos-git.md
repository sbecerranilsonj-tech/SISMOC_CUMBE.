# Fase 3 datos, secretos y Git Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rotar credenciales, sacar `dump_data.json` del índice Git, fijar dependencias y propagar correcciones de seguridad al escritorio sin reescribir historial ni hacer push.

**Tech Stack:** Django ORM, PostgreSQL, Git, pip.

**Spec:** `C:/Users/USUARIO/AppData/Local/Temp/opencode/diseno-fase3-datos-git.md`

## Global Constraints
- No hacer `git push`.
- No borrar archivos del disco; `git rm --cached` solo quita del índice.
- No reescribir historial Git.
- No mostrar contraseñas en el chat; entregar por archivo local con permisos restringidos.
- No tocar datos de negocio; solo credenciales.
- Respaldo antes de cambiar contraseñas.

## Review Focus
- Usuarios deben poder entrar con las nuevas claves.
- `dump_data.json` debe dejar de aparecer en `git ls-files` pero seguir en disco.
- Dependencias deben quedar con versiones exactas verificables.
- Correcciones de seguridad deben existir en ambas ediciones.

### Task 1: Respaldo y rotación de contraseñas de usuario
- [ ] Respaldo de ambas BD.
- [ ] Generar contraseñas nuevas y aplicarlas a las cuentas reales en A y B.
- [ ] Escribirlas en archivo local con permisos restringidos; no imprimirlas.
- [ ] Verificar autenticación con cada cuenta nueva.

### Task 2: Git
- [ ] `git rm --cached dump_data.json` en el repo web; verificar con `git ls-files` que ya no está y que el archivo sigue en disco.

### Task 3: Rotar secretos restantes
- [ ] Nueva contraseña PostgreSQL + pgAdmin + token del agente; actualizar `.env`, compose y BD; no imprimir valores.

### Task 4: Dependencias
- [ ] Generar lock con versiones exactas desde el entorno instalado.
- [ ] Intentar hashes; si no se pueden obtener, documentarlo explícitamente.

### Task 5: Divergencia de seguridad
- [ ] Comparar archivos de seguridad entre A y B y copiar solo las correcciones faltantes.

### Task 6: Verificación final
- [ ] `manage.py check`, suites, `git status`, informe Markdown.
