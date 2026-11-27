# Recuperación del abordaje con datos reales

## Respaldo y límites

Antes de modificar archivos se copió el proyecto a:
`D:\2026_II\PRACTICAS_PRE\BACKUP_SISMOC_ABORDAJE_20261125_154811`.
Se compararon SHA-256 de main.dart, pubspec.yaml, views.py y test_buses_embarque.py con el respaldo: coinciden.

No se eliminaron carpetas, no se instalaron APK en teléfonos, no se ejecutaron migraciones en la base real ni se modificaron reservas, asignaciones o registros reales para probar.
Las fuentes originales recuperadas permanecen intactas en `recuperado_demo/fuentes/`.

## Recorrido recuperado

Referencia: capturas del 22/11/2026 aportadas por el usuario y `recuperado_demo/fuentes/embarque_demo.dart`.

1. **Panel de Abordaje:** fecha del servidor, saludo, totales, Hoy/Mañana/Todos, búsqueda, filtro por estado, ficha de viaje, capacidad y progreso.
2. **Manifiesto y Embarque:** pasajeros del viaje, búsqueda, estado, piso/asiento, DNI y puntos de recojo/bajada de Ventas; confirmación de identidad y boleto antes de embarcar.
3. **Manifiesto:** datos del viaje, conductores y DNI registrados, responsable asignado, lista completa, totales, espacios de firma e impresión PDF multipágina.

La tabla se desplaza horizontalmente en teléfonos: no se cortan ni se eliminan columnas para imitar el recorte de las capturas.
Se mantiene acceso al croquis anterior y a sus funcionalidades.

## Autorización

- El embarcador solo recibe operaciones donde está asignado.
- El conductor asignado puede consultar y modificar estados de embarque sin depender del indicador antiguo `permite_embarque_conductor`.
- Un conductor ajeno y un embarcador sin asignación no pueden acceder mediante la API.
- Ventas y Gestión mantienen sus permisos existentes.
- Se permiten verificaciones en viajes programados no históricos y en viajes en curso (incluidas rutas que atraviesan medianoche).
- Viajes cerrados, cancelados o anulados no admiten nuevas modificaciones.
- Se conserva la confirmación de identidad y boleto, la auditoría, el control de estado anterior y la idempotencia del evento.

No se autoriza al conductor a vender boletos, inventar reservas ni cambiar la ficha de un pasajero: modifica estados de embarque de reservas que Ventas haya registrado.

## Conexión y QR

El panel consulta `panel_abordaje`; el detalle consulta `abordaje`. Son acciones de lectura.
El cambio de estado usa la acción existente `embarcar` y solo se presenta como confirmado tras respuesta del servidor.
Si no se puede actualizar, la nueva pantalla deshabilita modificaciones; el croquis previo conserva su flujo offline.

La cámara ahora utiliza `mobile_scanner`, no el simulador recuperado. El QR debe contener exactamente la referencia del boleto registrada por Ventas (se normalizan espacios extremos y mayúsculas). No se inventa un esquema QR ni se interpretan URLs desconocidas.
El ingreso manual comparte la misma búsqueda y confirmación de identidad.
Debe probarse el permiso de cámara y una lectura real en teléfono antes de dar por validado el hardware.

## Manifiesto

`generarPdfReal` usa el conjunto de datos recibido del servidor. No reutiliza RUC, dirección, placa, DNI ni pasajeros ficticios del PDF DEMO.
El nombre predeterminado se toma de la empresa indicada en AGENTS.md. RUC y dirección se omiten si no están definidos en los ajustes Django `SISMOC_EMPRESA_RUC` y `SISMOC_EMPRESA_DIRECCION`; `SISMOC_EMPRESA_NOMBRE` permite configurar el nombre.

No se afirma que la empresa tiene autorización MTC a partir de un ejemplo de diseño.
Las firmas se dejan en blanco; un embarque no equivale a firma biométrica.
La leyenda aclara que es un manifiesto interno y no acredita transmisión oficial al MTC ni autorización administrativa.
El botón de impresión abre el servicio de impresión del dispositivo (también puede guardarse como PDF).

## Verificaciones

- 29 pruebas Django de abordaje, buses y descanso pasan usando `--settings=config.test_settings` (SQLite en memoria).
- 10 pruebas Flutter pasan: navegación, confirmación de identidad, persistencia por API ficticia, rechazo de boleto ajeno, solo consulta al cerrar, diseño a 360/390 px, texto ampliado y PDF de 130 pasajeros.
- Se ejecutaron además 55 pruebas AppTests: 54 pasan y permanece el fallo conocido `test_sales_page_and_embarkation_assignment`, que busca “Responsable de embarque” en la página antigua `/movil/ventas/`.
- `flutter analyze` no reportó errores de compilación ni warnings; sí avisos informativos de estilo/deprecación, incluidos avisos nuevos y anteriores. No es un análisis sin observaciones.
- Falta validación física de cámara, impresión y comparación visual final en los teléfonos. No se afirma que estén comprobadas por los tests.

## Archivos

- `movil/abordaje.py`: selección autorizada, contadores y datos del manifiesto.
- `movil/views.py`: acciones de API y permiso del conductor asignado.
- `mobile/lib/abordaje.dart`: las tres pantallas, validación, escáner e impresión.
- `mobile/lib/main.dart`: integración con Embarque/Ventas y acceso al croquis existente.
- `mobile/pubspec.yaml`, `mobile/pubspec.lock`, manifiesto Android: dependencias y permiso opcional de cámara.
- `movil/test_abordaje_real.py`, pruebas existentes de buses/app y `mobile/test/abordaje_test.dart`: cobertura aislada.
