# Diseño: botón «Todas las solicitudes» en el panel del aplicativo

## Intento y por qué

El panel `Aplicativo de trabajadores` (`movil/panel.html`) tiene un diálogo de
«Solicitudes pendientes» con botones Aprobar/Rechazar, pero **ningún botón lo abre**
(no existe ningún elemento con `data-open-solicitudes`). El usuario pidió un botón
que muestre **todas las solicitudes registradas** — pendientes, aprobadas y
rechazadas — y que permita decidir sobre las pendientes desde el mismo diálogo.

## Alcance

- Solo la edición web (`movil/panel.py`, `templates/movil/panel.html`).
- Las pruebas del panel y de revisión de solicitudes.
- No se toca la lógica de negocio de aprobación (`movil/gestion.py`).
- No se toca la edición escritorio: el panel móvil es exclusivo de la web
  (`MOVIL_HABILITADO = False` en escritorio).

## Permisos

El panel ya exige `request.user.rol in GESTION` (`movil/panel.py:27`). No se añade
ninguna comprobación nueva: el botón y el diálogo quedan visibles solo para
administración/contabilidad/gerencia. La aprobación sigue protegida por
`gestionar('revisar_solicitud', ...)` (rol GESTION, no aprobación propia, solo si
está PENDIENTE).

## Enfoques considerados

1. **Añadir un diálogo nuevo y dejar el actual**: más código y dos formularios de
   aprobación distintos. Descartado por duplicación.
2. **Reutilizar el diálogo existente y ampliarlo a todos los estados**: un solo
   botón, una sola tabla, un solo formulario de decisión. Elegido. Además hace
   alcanzable un diálogo que hoy está muerto.
3. **Página independiente con filtros y paginación**: útil con miles de filas, pero
   innecesario para el volumen actual y rompe el patrón de paneles del proyecto.
   Descartado.

## Diseño elegido

### Backend (`movil/panel.py`)

- Mantener `solicitudes` (pendientes) para no romper nada existente.
- Añadir al contexto `todas_solicitudes`: todas las `Solicitud` con
  `select_related('perfil__trabajador', 'perfil__usuario', 'revisado_por')`,
  ordenadas por `-creado`. Sin límite de filas: el usuario pidió «todas».
- La acción `revisar_solicitud` existe y no cambia.

### Frontend (`templates/movil/panel.html`)

- Añadir en la fila de «Configuración», junto a *Regla de descanso* y *Cuentas de
  Boletería por sede*, un botón **«Todas las solicitudes»** con
  `data-open-solicitudes`.
- Renombrar el diálogo de «Solicitudes pendientes» a **«Todas las solicitudes»**.
- Mostrar una tabla con: fecha, trabajador, tipo, desde/hasta, estado, respuesta y
  revisado por. El estado se muestra con etiqueta visual por color.
- Para cada fila PENDIENTE, mostrar el mismo formulario POST de hoy con:
  `accion=revisar_solicitud`, `id`, `respuesta` (opcional), `turno` (opcional,
  necesario solo en `CAMBIO_HORARIO` si `s.datos` no lo trae) y botones
  **Aprobar** / **Rechazar**.
- Para APROBADO/RECHAZADO: solo lectura (fecha de revisión y respuesta).
- Si no hay solicitudes: mensaje «No hay solicitudes registradas.».

### Comportamiento

- Al aprobar/rechazar, el POST sigue el flujo existente: actualiza estado,
  respuesta, `revisado_por`, crea `Aviso` y `Auditoria`, y recarga el panel.
- Los estados ya registrados no se pueden volver a decidir: el servidor responde
  409 y el botón no aparece en esas filas.

## No incluido

- Filtros por sede/estado, paginación ni exportación.
- Cambios en la app móvil Flutter.
- Cambios en el escritorio.

## Verificación

- Prueba nueva: el panel contiene el botón «Todas las solicitudes» y la tabla
  incluye una solicitud APROBADA, una RECHAZADA y una PENDIENTE.
- Prueba existente de aprobación/rechazo sigue en verde.
- `manage.py check` y la suite del panel en verde.
- Comprobación visual en `http://192.168.18.75:8000/movil/panel/`.
