# Todas las solicitudes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer alcanzable y ampliar el diálogo de solicitudes del panel para mostrar pendientes, aprobadas y rechazadas, permitiendo decidir sobre las pendientes en el mismo lugar.

**Architecture:** El panel ya es solo de GESTION. Se reutiliza el diálogo existente (hoy sin botón que lo abra), se añade un botón en la fila de Configuración y se pasa un queryset con todos los estados al template. La acción `revisar_solicitud` de `movil/gestion.py` no cambia.

**Tech Stack:** Django 5, templates HTML con `<dialog>`, unittest con `config.test_settings`.

**Spec:** `docs/superpowers/specs/2026-11-27-todas-las-solicitudes-design.md`

## Global Constraints

- No tocar `movil/gestion.py` ni la lógica de aprobación, permisos, avisos o auditoría.
- No añadir permisos nuevos: el panel ya exige `rol in GESTION`.
- No tocar la edición escritorio ni la app Flutter.
- Sin límite de filas: el usuario pidió «todas» las solicitudes.
- Mantener `solicitudes` (pendientes) en el contexto por compatibilidad.

## Review Focus

- Diálogo actual sin opener: el botón nuevo debe abrirlo — cubierto en Task 2.
- Estado APROBADO/RECHAZADO sin botones de decisión — cubierto en Task 2.
- Solicitudes sin respuesta ni revisor: la tabla debe mostrar guiones, no fallar — cubierto en Task 2.
- Aprobación de su propia solicitud: ya bloqueada en `gestion.py`; se verifica en Task 3.
- Usuario no GESTION: el panel ya devuelve 403; se verifica en Task 3.

---

### Task 1: Contexto con todas las solicitudes

**Files:**
- Modify: `movil/panel.py:131` (`return render(...)`)
- Test: `movil/test_panel_operativo.py`

**Interfaces:**
- Consumes: `Solicitud` desde `.models`, ya importado en `movil/panel.py:20`.
- Produces: `contexto['todas_solicitudes']` (queryset ordenado por `-creado`), usado por Task 2.

- [ ] **Step 1: Write the failing test**

Añadir a `PanelOperativoTests`:

```python
    def test_panel_expone_todas_las_solicitudes(self):
        gestor, perfil = self.gestor()
        dia = timezone.now().date()
        Solicitud.objects.create(perfil=perfil, tipo='PERMISO', desde=dia, hasta=dia,
                                 detalle='Solicitud aprobada de prueba', estado='APROBADO')
        Solicitud.objects.create(perfil=perfil, tipo='VACACIONES', desde=dia, hasta=dia,
                                 detalle='Solicitud rechazada de prueba', estado='RECHAZADO')
        respuesta = self.client.get('/movil/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['todas_solicitudes']), 2)
        self.assertEqual(respuesta.context['todas_solicitudes'][0].estado, 'RECHAZADO')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec sismoc-cumbe-web python manage.py test movil.test_panel_operativo.PanelOperativoTests.test_panel_expone_todas_las_solicitudes --settings=config.test_settings --noinput`
Expected: FAIL con `KeyError: 'todas_solicitudes'`.

- [ ] **Step 3: Implement the context**

En `movil/panel.py`, en el `return render(...)` añadir:

```python
'todas_solicitudes':Solicitud.objects.select_related(
    'perfil__trabajador','perfil__usuario','revisado_por').order_by('-creado'),
```

- [ ] **Step 4: Run test to verify it passes**

Run el mismo comando del Step 2.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add movil/panel.py movil/test_panel_operativo.py
git commit -m "Exponer todas las solicitudes en el panel"
```

---

### Task 2: Botón y diálogo «Todas las solicitudes»

**Files:**
- Modify: `templates/movil/panel.html:8-24` y `templates/movil/panel.html:68`

**Interfaces:**
- Consumes: `contexto['todas_solicitudes']` de Task 1.
- Produces: botón con `data-open-solicitudes` y diálogo `[data-solicitudes-dialog]`.

- [ ] **Step 1: Write the failing test**

Añadir a `PanelOperativoTests`:

```python
    def test_panel_muestra_boton_y_estados_de_todas_las_solicitudes(self):
        gestor, perfil = self.gestor()
        dia = timezone.now().date()
        Solicitud.objects.create(perfil=perfil, tipo='PERMISO', desde=dia, hasta=dia,
                                 detalle='Solicitud aprobada de prueba', estado='APROBADO')
        Solicitud.objects.create(perfil=perfil, tipo='VACACIONES', desde=dia, hasta=dia,
                                 detalle='Solicitud rechazada de prueba', estado='RECHAZADO')
        respuesta = self.client.get('/movil/')
        self.assertContains(respuesta, 'Todas las solicitudes')
        self.assertContains(respuesta, 'data-open-solicitudes')
        self.assertContains(respuesta, 'Solicitud aprobada de prueba')
        self.assertContains(respuesta, 'Solicitud rechazada de prueba')
        self.assertContains(respuesta, 'APROBADO')
        self.assertContains(respuesta, 'RECHAZADO')
```

- [ ] **Step 2: Run test to verify it fails**

Run: el test del Step 1.
Expected: FAIL (no aparece «Todas las solicitudes» ni el botón).

- [ ] **Step 3: Implement button and dialog**

En la fila de Configuración (`panel.html:10-13`) añadir:

```html
<button type="button" class="cd-button cd-secondary" data-open-solicitudes>Todas las solicitudes</button>
```

Reemplazar el diálogo actual (`panel.html:15-24`) por uno con:
- título «Todas las solicitudes»;
- `<table class="cd-table">` con columnas Fecha, Trabajador, Tipo, Desde/Hasta, Estado, Respuesta, Revisado por;
- iteración sobre `todas_solicitudes` con `{% for s in todas_solicitudes %}`;
- para `s.estado == 'PENDIENTE'`, el formulario POST existente (`accion=revisar_solicitud`, `id`, `respuesta`, `turno`, botones Aprobar/Rechazar);
- para los demás estados, solo lectura;
- `{% empty %}<p>No hay solicitudes registradas.</p>{% endfor %}`.

Dejar el `bind('[data-open-solicitudes]', ...)` existente en `panel.html:68`.

- [ ] **Step 4: Run test to verify it passes**

Run: el test del Step 1.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/movil/panel.html movil/test_panel_operativo.py
git commit -m "Añadir botón de todas las solicitudes al panel"
```

---

### Task 3: Regresión y verificación final

**Files:** ninguno nuevo (solo ejecución).

- [ ] **Step 1: Ejecutar pruebas existentes de solicitudes**

Run:

```bash
docker exec sismoc-cumbe-web python manage.py test movil.test_panel_operativo movil.tests --settings=config.test_settings --noinput
```

Expected: OK. Nota: `movil.test_panel_operativo` ya pasa en la edición web; falla en escritorio por configuración de prueba que excluye `/movil/` y no se toca aquí.

- [ ] **Step 2: Verificar check y health**

Run:

```bash
docker exec sismoc-cumbe-web python manage.py check
```

Expected: `System check identified no issues`.
Además: `http://127.0.0.1:8000/health/` → `ok`.

- [ ] **Step 3: Verificación visual**

Abrir `http://192.168.18.75:8000/movil/`, pulsar «Todas las solicitudes» y confirmar que aparecen los tres estados y que las filas aprobadas/rechazadas no tienen botones de decisión.

- [ ] **Step 4: Commit final si hay ajustes**

Solo si hicieron falta correcciones menores.
