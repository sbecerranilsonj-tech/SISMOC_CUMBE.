# Aplicativo SISMOC · El Cumbe

Una app Flutter con cuentas individuales y funciones según el rol de SISMOC. El servidor Django mantiene la información; la administración conserva la revisión de jornadas y pagos. Esta entrega es una versión local de desarrollo, no una certificación de seguridad, biometría ni cumplimiento SUTRAN.

## Verificación de esta entrega

Pasaron **93 pruebas del servidor**: 25 del módulo móvil y 68 de conductores. Cubren autenticación, permisos, marcas, comisiones, solicitudes, relevos, descanso, importaciones reales de Excel y embarque. Las tablas nuevas se aplicaron a la base SQLite local después de respaldarla. El código Dart pasó por el formateador y comprobación de sintaxis del SDK; esto no sustituye el análisis de tipos ni las pruebas de Android.

**No se generó ni se probó un APK.** La revisión automática del entorno bloqueó la ejecución de Flutter por un intento de acceso a `169.254.169.254` (metadatos de instancia). No se autorizó ese acceso ni se siguió intentando compilar. Quedan pendientes `flutter analyze`, pruebas de widgets, compilación y ejecución en emulador/teléfono desde un entorno donde Flutter pueda funcionar sin consultar ese servicio. No confundir las pruebas del servidor con pruebas de Android.

## Ejecutar en la laptop

Desde la carpeta raíz del proyecto, usando el Python del entorno de SISMOC:

```powershell
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Abrir **Aplicativo de trabajadores** en el menú de administración (`/movil/`). Vincular las fichas con sus cuentas existentes. Generar un código de activación y entregarlo personalmente. No se crean usuarios ficticios ni se modifican contraseñas de cuentas reales automáticamente. También se puede habilitar por consola:

```powershell
python manage.py habilitar_app nombre_usuario --trabajador 12 --conductor 4
```

Para un celular perdido: agregar `--restablecer`. Se revocan todas las sesiones previas. El código de activación vence en 24 horas y funciona una vez. El código CUM del trabajador se conserva.

Preparar Flutter, desde la raíz:

```powershell
cd mobile
flutter pub get
flutter analyze
flutter test
flutter devices
flutter run
```

Si falta la carpeta Android, ejecutar primero `./tool/preparar.ps1`. El SDK de Android debe estar configurado y sus licencias aceptadas. Abrir un dispositivo en Android Studio → Device Manager o conectar el teléfono con depuración USB. El emulador accede a Django con `http://10.0.2.2:8000`; un teléfono físico usa `http://IP-DE-LA-LAPTOP:8000`, en la misma red. El cortafuegos de Windows debe permitir ese acceso privado. El APK de producción requiere HTTPS. Para APK de pruebas: `flutter build apk --debug`.

## Funciones implementadas

| Función | Comportamiento |
| --- | --- |
| Cuenta | Código único, activación temporal, contraseña de SISMOC, dispositivo vinculado, tokens con hash y revocación, limitación de intentos |
| Asistencia | Ingreso, salida/retorno de refrigerio y salida; GPS reciente y preciso dentro de radio por sede; secuencia de eventos y jornada nocturna |
| Fuera de sede | Comisión autorizada con fechas, motivo y excepción facial delimitada; especialmente mecánicos |
| Sin conexión | Cola local en almacenamiento seguro para marcas y verificaciones; las marcas diferidas requieren confirmar su hora antes de entrar a asistencia |
| Horas | Horarios y jornadas calculadas por el motor existente; recepción técnica separada de aprobación contable |
| Solicitudes | Permiso, vacaciones, cambio de horario y corrección; fecha anterior para las planificadas, emergencia explicada; no autoaprobación |
| Ventas | Importación de Excel de itinerarios, comparación, conservación de viajes ya importados y conflictos explícitos |
| Asignación | Dos conductores distintos, comprobación de cruces con llegada prevista, bloqueo configurable de descanso |
| Viaje | Salida compartida, conductor que maneja, relevo solicitado y aceptado, llegada compartida, fin individual de labores |
| Calendario web | Las salidas nuevas de la app aparecen como PR y no generan pago antes de finalizar; los reportes históricos conservan su comportamiento |
| Embarque | Asientos agrupados por piso, búsqueda por asiento/documento/nombre, verificación y estados; comparación del estado anterior para evitar sobrescrituras |
| Pasajeros | Adaptador CSV de prueba, referencias únicas, reimportación conservadora y notificación de puntos antes del viaje |
| Incidencias | Reportes asociados al viaje y aviso a ventas/administración; estados recibido, en atención y resuelto |
| Vueltas | Solo operaciones móviles finalizadas: 2 trayectos = 1 vuelta, estimado S/20 por vuelta; se muestran pagos registrados aparte |
| Manifiesto | CSV interno compartible; no acredita envío oficial al MTC |

API JSON bajo `/movil/api/<accion>/`, POST con `Authorization: Bearer TOKEN`. La sesión web no autoriza esos endpoints. El panel web sí usa sesión normal y CSRF. Los eventos de viaje y marcaciones usan UUID para reintentos. Para pruebas del servidor: `python manage.py test movil --settings=movil.test_settings`.

## Configuración antes de pruebas operativas

### Ajustes de uso del 12 de noviembre

- El ojo de los campos permite mostrar u ocultar las contraseñas al crearlas, confirmarlas e iniciar sesión.
- Los conductores no requieren sede. Su DNI es opcional; se almacena como nulo cuando no se proporciona, sin inventar identificaciones. Aplicar las migraciones con `docker compose exec web python manage.py migrate` desde la raíz del proyecto antes de habilitar conductores sin DNI.
- En Cuenta → Mi ubicación para pruebas, el trabajador puede consultar y copiar las coordenadas GPS del teléfono. En el panel web, Zonas de trabajo y pruebas permite pegar esas coordenadas o solicitar la ubicación del navegador. La opción Solo un trabajador limita la zona a la cuenta elegida. Las coordenadas de una laptop pueden ser imprecisas: comprobar ubicación y precisión antes de usarlas. No se rastrea al trabajador continuamente.
- Los campos de trabajador de comisiones y pagos muestran sugerencias al escribir; los conductores mantienen su catálogo separado.
- Las marcas capturadas sin conexión generan una jornada pendiente y se confirman en Asistencia → detalle del día. Confirmar una marca no aprueba automáticamente la jornada. El antiguo formulario del panel móvil y la API genérica ya no permiten validarlas allí.
- Ventas / Boletería dispone de `/movil/ventas/` para subir y comparar itinerarios, reemplazar conductores, asignar el responsable de embarque y cargar el CSV provisional de pasajeros. Sus reportes operativos se reciben en la app de Ventas y pueden marcarse como recibidos, en atención o resueltos. La bandeja sigue siendo por sincronización, no push.
- Al habilitar una cuenta de personal se puede seleccionar su función: Personal, Ventas / Boletería o Encargado de embarque. No concede roles administrativos. Para conductores la función se obtiene de su ficha. La app de embarque muestra los viajes asignados; los conductores ven sus viajes y pueden verificar pasajeros cuando Ventas habilita esa función.

Verificación de estos cambios: 46 pruebas del módulo móvil y 68 de conductores aprobadas; análisis estático Dart sin errores, con avisos informativos. La nueva prueba del ojo de contraseña queda incluida para ejecutarse con `flutter test`; no se ha verificado en el teléfono desde este entorno.

### Activación en el celular

El selector del panel busca trabajadores y conductores mientras se escribe (hasta ocho sugerencias). Las fichas vinculadas explícitamente a un conductor aparecen una sola vez, como conductor. No se fusionan personas solo porque coincidan sus nombres. Para un conductor sin cuenta ni ficha de personal, la habilitación pide su DNI real y sede, crea su acceso en el catálogo de conductores y conserva separado el catálogo de Personal; un DNI que ya corresponde a otra ficha requiere revisión de identidad.

En el panel web, seleccionar una ficha existente y pulsar **Habilitar acceso y generar código**. El código temporal nuevo incluye un prefijo numérico seguido de un punto; los códigos de la versión anterior deben regenerarse una vez para usar este flujo.

En la app, configurar el servidor y pulsar **Activar mi cuenta**. El popup pide solo el código temporal, lo valida y muestra automáticamente el código CUM del trabajador. Luego solicita una nueva contraseña y su confirmación. La validación dura diez minutos, se vincula al dispositivo y deja de funcionar al consumir o reemplazar el código. Al guardar no se abre una sesión: la app recuerda el código CUM en almacenamiento seguro y vuelve al ingreso para solicitar solo la contraseña. Nunca se guarda la contraseña en el teléfono. Los códigos recordados se separan por dirección de servidor.

No se necesita ingresar manualmente el código CUM. La activación mantiene el límite de intentos y no permite reutilizar códigos. La validación y el establecimiento de contraseña requieren conexión con SISMOC.

1. Vincular usuario, trabajador y conductor correctos; no cruzar fichas de otras personas.
2. Registrar coordenadas y radio reales de cada sede. La ubicación y su margen de precisión deben estar dentro del radio. Una zona sin asignación individual se aplica a su sede; las zonas individuales se asignan desde administración Django.
3. Configurar horarios en el sistema existente. Las marcas móviles se publican en Asistencia, conservando su origen; Yaneli revisa las jornadas.
4. Importar un Excel con conductores ya identificados. Las filas se distribuyen automáticamente; nombres desconocidos y cambios ambiguos requieren corrección.
5. Asignar permiso de embarque al responsable del viaje. El conductor solo ve/verifica documentos si tiene esa función habilitada.
6. Confirmar con la empresa la política de descanso y recién activarla. Las 8 horas no se presentan como una norma legal verificada. El descanso se inicia cuando cada conductor declara fin de labores fuera del bus, no por el relevo a bordo.

CSV provisional de pasajeros, UTF-8:

```csv
referencia,nombre,documento,piso,asiento,origen,destino,punto
RESERVA-001,PASAJERO DE PRUEBA,00000000,1,4,Chiclayo,Cajamarca,Terminal Chiclayo
```

Usar solo datos ficticios en pruebas. El número de documento de este ejemplo no corresponde a una identificación validada. La ausencia de una reserva en otra carga no la elimina. Hasta conocer los tramos reales, los asientos repetidos se bloquean; no se presume que están libres por una inasistencia.

## Integraciones y límites que siguen pendientes

- **Reconocimiento facial y prueba de vida:** no hay un motor de identidad implementado. Si una cuenta lo exige, no se acepta una supuesta verificación enviada por el teléfono: la marca se bloquea salvo comisión con excepción autorizada. Requiere enrolamiento supervisado, protección de plantillas, consentimiento y pruebas con celulares reales. No se guardan selfies como sustituto de identidad verificada.
- **GPS manipulado:** geocerca y precisión no prueban por sí solas identidad o presencia. Falta atestación del dispositivo y política empresarial para señales de ubicación simulada. No se rastrea continuamente al trabajador.
- **Pasajeros reales:** la empresa debe entregar el formato de exportación y plano de buses. El croquis actual agrupa los asientos importados por piso; no reproduce un plano físico desconocido. QR y transmisión oficial están pendientes.
- **Reimportaciones complejas:** sin ID externo estable no se puede inferir todo cambio de fecha, ruta o bus. Los posibles cambios se rechazan para revisión; el archivo no deshace una sustitución manual o un viaje ya iniciado. Confirmar el identificador del proveedor antes de automatizar todos los casos.
- **Notificaciones:** bandeja al sincronizar, sin servicio push en segundo plano todavía.
- **Correcciones de asistencia:** se tramitan con la revisión existente; no se inventa una hora ni se aprueba económicamente desde una solicitud sin aplicar su corrección.
- **Pagos históricos:** el resumen móvil cuenta operaciones finalizadas en el mes y muestra pagos del mismo período. Los itinerarios históricos existentes mantienen sus cálculos en el calendario web; no se convierten en llegadas reales inventadas. Aún falta conciliación de pagos parciales y períodos que atraviesan meses.
- **Conducción y normativa:** registrar relevos permite observar períodos, pero aún falta motor completo de límites diarios/nocturnos, acumulados y normativa versionada. El bloqueo de descanso interno no sustituye esa validación.
- **Servidor público:** no desplegado. Pruebas locales primero; luego HTTPS, copias, PostgreSQL, monitoreo, política de datos y presupuesto de la empresa.

No usar esta versión para bloquear físicamente un bus, autorizar conducción legal o liquidar remuneraciones sin revisión. Los estados sirven como control del sistema; no sustituyen las decisiones operativas de la empresa.
