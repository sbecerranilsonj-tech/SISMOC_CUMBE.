# Gestión de conductores · Sprint 03

## Activación

El módulo comparte la plantilla, el tema y el menú principal de SISMOC.

```powershell
docker compose exec web python -c "import xlrd, openpyxl; print('Lectores disponibles')"
docker compose exec web python manage.py migrate
docker compose restart web
docker compose exec web python manage.py test conductores bancos
```

Si falta xlrd: `docker compose exec web python -m pip install "xlrd>=2.0.2,<3.0"`.
La dependencia ya figura en requirements.txt para reconstrucciones futuras.

Abrir `/conductores/`. No se cargan los documentos reales automáticamente en la base de producción.

## Flujo

El menú lateral contiene Importar itinerarios y Control de conductores. En Control, el botón Conductores reemplaza el recuadro El Cumbe y abre el listado y la configuración en un popup. La importación y validación se realizan en la misma pantalla, sin los tres botones superiores. La antigua ruta de validación redirige al importador conservando los filtros.

Importar ofrece tarjetas de mes según las fechas reales de las salidas, filtro de archivo y búsqueda por bus, recorrido o conductor. La tabla contiene las filas originales ordenadas por fecha y hora: recorrido, dos conductores, vendidos por piso, total, capacidad y estado. El bus se conserva en los datos, pero no aparece como columna. Las pestañas separan todas, pendientes de validar, validadas y anuladas. Un reporte que cruza meses aparece en ambos, pero mantiene una única importación.

En Importar, el botón flotante inferior derecho abre el selector de archivos y envía el formulario al elegir uno, sin popup de carga intermedio. Al terminar se abre la tabla filtrada por el archivo recién importado. La confirmación está debajo de la tabla y pasa el reporte completo a Control, conservando los bloqueos por nombres sin identificar, duplicados y demás incidencias. Los importes/cantidades ausentes se muestran sin inventar pisos o ventas; los ceros reales se conservan.

«Reconocer conductores ya registrados» actualiza asociaciones pendientes por coincidencia exacta normalizada, sin crear fichas nuevas. Los reportes validados permanecen bloqueados.

El popup Conductores muestra una lista sencilla por apellidos, búsqueda y el botón Registrar nuevo en la cabecera. Cada fila tiene Configurar, que abre un segundo popup individual: datos personales, vacaciones/descansos/permisos/licencias y situaciones registradas. El conductor de la situación queda fijado por la ficha abierta. Al guardar se actualizan el listado y el calendario sin cerrar las ventanas, conservando los filtros; los botones de detalle del calendario siguen funcionando tras el refresco. Se preserva el nombre original y las identidades de importación. Los cambios se auditan; no se permite crear un duplicado por nombre ni superponer situaciones. Requiere las migraciones 0002 y 0003 de conductores. Las licencias genéricas anteriores se conservan; las nuevas deben especificar con o sin goce. Control muestra el calendario y los conflictos, con LC y LS para distinguir ambas licencias.

1. Importar XLS, XLSX o XLSM del reporte de itinerarios (hoja Reporte, hasta 20 MB).
2. Pulsar «Registrar conductores del reporte» para crear sus fichas operativas y reconocer las existentes por nombre normalizado. Esta acción asigna todas sus salidas sin modificar el personal de otras áreas ni crear DNI. Si un nombre coincide con varias fichas, se bloquea el grupo y se pide una revisión individual.
3. Validar el reporte. Bloquea errores de lectura, conductores sin identificar, la misma persona en ambos puestos y salidas duplicadas.
4. Consultar Control de conductores con un período de hasta 62 días, incluido el corte 31/07–30/08. Pulsar una celda abre sus viajes con procedencia.
5. Registrar descanso, vacaciones, permiso o licencia por período y motivo. Las situaciones superpuestas se rechazan. Si una situación coincide con viajes se muestra conflicto. Es posible anular el registro; se conserva su auditoría.

## Cálculo

Cada salida activa confirmada suma una asignación a cada conductor, en cualquiera de las dos columnas. Cambiar de compañero, bus o posición no altera el conteo individual. Una asignación = un trayecto = 0.5 vueltas equivalentes. Se cuenta por fecha de salida; no por la fecha de llegada.

| Trayectos diarios | Presentación | Vueltas |
| --- | --- | --- |
| 1 | Hora de salida | 0.5 |
| 2 | X | 1 |
| 3 | XX | 1.5 |
| 4 o más | Cantidad de trayectos | Cantidad / 2 |

Equivalencia observada al cruzar ambos documentos. XX no debe presentarse como cuatro trayectos. El conteo de pares no certifica un regreso a la misma ciudad.

Un día sin viajes ni situación es pendiente, nunca descanso o ausencia inferidos. Los registros anulados no suman. Los pendientes no son faltas para planilla.

El calendario contiene únicamente el conductor y sus días. Debajo se muestra otra tabla con trayectos, vueltas, días con viajes, descansos, HORA, X, XX y pendientes; no incluye columnas de vacaciones ni permisos. HORA cuenta días con un trayecto, X días con dos y XX días con tres, sin convertir la hora registrada en duración de trabajo.

El orden del resumen es: trayectos, días con viajes, descansos, vueltas, pago por vueltas, HORA, X, XX y pendientes. El pago es el número de vueltas × S/ 20.00, calculado con Decimal y dos decimales. Ejemplo: 21 vueltas = S/ 420.00. Es el pago por vueltas, no una liquidación completa de planilla.

Motivo es opcional en los formularios. Descuento es una situación disponible en ficha y calendario, con marca DS; clasifica el día y no presupone un importe monetario de deducción. La migración 0004 actualiza ambas opciones sin eliminar los registros existentes.

Al pulsar un día pendiente (guion), se puede guardar una situación para esa fecha directamente en el popup. Se valida que no haya viajes confirmados ni otra situación superpuesta. El calendario y el resumen se actualizan al guardar. El detalle de los viajes no muestra ventas ni capacidad; esos datos siguen conservados en la importación.

## Integridad y alcance

- Huella SHA-256 del archivo para evitar repetir una importación idéntica.
- Clave de salida: fecha, hora, bus, origen y destino. La confirmación tiene restricción única en base de datos para impedir duplicados entre reportes, incluso con concurrencia.
- Se conserva el contenido original por fila, el Excel privado, el importador, el validador y las vinculaciones auditadas.
- Un reporte validado no permite cambiar identidades desde su revisión.
- Acceso limitado a administrador, contadora o gerente activos. Los archivos originales se entregan por una vista con estos permisos, fuera de media público.
- El control es independiente de las marcaciones biométricas. No modifica jornadas ni calcula remuneraciones.
- No calcula horas efectivas de conducción, llegadas ni descanso entre servicios. No implementa GPS ni alertas legales: requieren datos de finalización/relevos y una regla confirmada.

## Datos para control de pasajeros

Cada salida conserva en `original.comercial` capacidad, vendidos de primer piso y vendidos de segundo piso, además de todas las columnas originales, incluidos los importes. La revisión de la importación muestra estas cantidades y el total. El detalle diario de Control se limita a la información del viaje. Los datos ausentes no se convierten en cero. Las cantidades se guardan por salida, sin duplicarlas por tener dos conductores.

Estos totales permitirán comparar ventas y embarques cuando exista el módulo de pasajeros. No contienen la lista individual de pasajeros, asientos o puntos de embarque: esa identificación requiere croquis/manifiesto o exportación del sistema de ventas.

## Recuperación XLS

Se intenta la lectura normal con xlrd. Si el contenedor OLE es rechazado, se recupera de forma limitada su flujo Workbook y se vuelve a interpretar con xlrd. Se validan sectores, ciclos y longitudes; el original no se modifica. Si ambos intentos fallan se informa el tipo y mensaje del lector y se ofrece guardar como XLSX desde Excel. Los errores de base de datos y de acceso a archivos se presentan por separado.

## Verificación

Pruebas del parser, firmas de encabezado, archivos XLSX, conteo individual, cambio de compañero, anulados, validación idempotente, duplicados, períodos, permisos, vacaciones, conflictos, auditoría e integración de las plantillas con el menú principal.

En un entorno sin Docker o con librerías nativas incompatibles, los tests pueden ejecutarse con SQLite y rutas auxiliares. Esto verifica el módulo pero no sustituye la activación y prueba en PostgreSQL con las dependencias del contenedor.


### Calendario y exportación

Desde una celda sin viajes se puede registrar una situación con fechas Desde/Hasta.
Todos los días del rango se actualizan juntos. Al editar, las fechas que quedan fuera
del rango conservan su situación anterior; no se admiten cruces con viajes confirmados
ni situaciones superpuestas. La lista de importación respeta la fila original del Excel
(dentro de cada archivo).

El botón «Descargar Excel · calendario y resumen» exporta el período y la búsqueda
actuales a un XLSX con dos hojas, encabezados, colores, paneles inmovilizados, totales
y configuración de impresión. Los importes se calculan a S/ 20 por vuelta.


### Salidas sin ventas y confirmación operativa

Las salidas con total de pasajes explícitamente igual a cero quedan como SV
(sin ventas, por confirmar). Conservan conductores y fecha, pero no aportan
trayectos, vueltas, HORA/X/XX ni pago. Una venta basta para mantener el cálculo
habitual: no se impone un mínimo de ocupación. Los datos comerciales ausentes
no se convierten en cero.

Desde el detalle del calendario se puede confirmar que una salida sin ventas
se realizó o marcarla como cancelada (C). Ambas decisiones se auditan; los datos
originales permanecen intactos. Una anulación del reporte original no se puede
revertir desde esta opción. La confirmación de salida realizada se bloquea si
hay situaciones registradas para los conductores en esa fecha.

Los conductores sin asignaciones ni situaciones en el período se ocultan del
calendario. El resumen muestra a todos los conductores del catálogo, con todas sus
columnas en cero cuando no tienen actividad; respeta la búsqueda por nombre. Una asignación SV/C sí se
muestra, aunque su pago sea cero. El Excel aplica los mismos criterios.

Activación: `python manage.py migrate conductores` (migración 0005). Las
importaciones existentes se recalculan al consultarlas, sin volver a subir el archivo.

La hoja de resumen del Excel también incluye a los conductores sin actividad,
con valores numéricos en cero. La hoja de calendario conserva sus filas habituales.

El panel «Salidas por confirmar» reúne las salidas SV del período y búsqueda
actuales, sin duplicarlas por conductor. Sus decisiones actualizan a ambos
conductores. Los días con viajes válidos y salidas SV conservan su hora/X/XX
y muestran una insignia SV con la cantidad de asignaciones por confirmar.
