# Consulta y revisión de asistencia

## Dashboard y huellero

El menú tiene dos apartados independientes. **Dashboard** reúne estadísticas de asistencia, personal y servicios registrados, con selección de fechas. Incluye espacios identificados como pendientes para los indicadores de flota y conciliación bancaria de próximos sprints.

**Huellero en tiempo real** muestra los eventos biométricos de hoy, del más reciente al más antiguo, con un máximo de 100 filas. Una persona puede aparecer varias veces porque cada fila es una marcación. La lista consulta los registros recibidos cada diez segundos mientras el apartado está visible; deja de actualizarse al cambiar de sección o esconder la pestaña. La consulta de conexión es una acción independiente y la descarga física del equipo sigue pendiente de integración. El registro manual por DNI conserva su origen separado y se consulta en Asistencia.

En el menú **Asistencia & HH.EE.**, seleccione las fechas inicial y final. Puede filtrar por sede, trabajador, estado de asistencia y revisión. El periodo puede abarcar dos meses. La tabla muestra 30 jornadas por página; el resumen y la exportación consideran todos los resultados filtrados.

## Administración

1. Abra **Ver detalle** para comprobar marcaciones, origen, intervalos de trabajo y refrigerio.
2. Asigne un turno a la jornada cuando corresponda. La asignación no modifica el turno habitual del trabajador.
3. Si el equipo reportó un tipo de evento equivocado, registre su corrección con motivo. El evento original se conserva.
4. Registre incidencias y propuestas de ajuste. Quedan pendientes de aprobación y no alteran los totales mientras no se aprueben.
5. Use **Marcar como observado** para solicitar revisión. Consulte el historial para conocer responsables y fechas.
6. En la bandeja de pendientes puede asociar marcas sin identidad. La asociación no cambia el identificador original. Registre una jornada sin horas si necesita documentar un día que no tenga resumen, por ejemplo vacaciones.

## Contabilidad y Gerencia

1. Revise los tramos y compare los tiempos reconstruidos con los valores guardados.
2. Compruebe y apruebe las incidencias y ajustes. Aprobarlos no aprueba automáticamente la jornada.
3. Apruebe la jornada cuando se hayan resuelto los bloqueos. Las jornadas con vacaciones o permisos sin marcas requieren la incidencia correspondiente de día completo aprobada.
4. Consulte el resumen por trabajador. Las horas se expresan en decimales: 2,50 h equivale a 2 h 30 min. El refrigerio se muestra en HH:MM:SS.
5. Exporte el resumen como CSV, compatible con Excel. Incluye recuentos de aprobadas, pendientes y observadas; no se presenta como un cierre aprobado cuando quedan pendientes.
6. Para cerrar un periodo pasado, revise todas sus jornadas, quite las incidencias pendientes y confirme el cierre. El cierre siempre abarca todas las sedes y trabajadores entre las fechas elegidas, independientemente de los demás filtros. Guarda los resultados y bloquea cambios desde los flujos del sistema.

Administración puede proponer y observar. Contabilidad y Gerencia pueden aprobar y cerrar. Los superusuarios conservan facultades de aprobación. Los demás roles solo consultan su propia asistencia.

## Interpretación de los resultados

En **Ver detalle**, el **Cuadro de control diario · Formato del Excel** muestra código del trabajador, fecha y hora, evento, duración entre marcas, refrigerio, jornada base, saldo, extras al 25 % y 35 %, nocturnas y feriado o descanso. Los tiempos se expresan en HH:MM:SS. La base es fija de **08:00:00** de trabajo efectivo, independientemente de la duración del turno; los totales reconstruidos requieren eventos completos y clasificados. Un dato insuficiente aparece como **Por revisar**. El saldo negativo muestra tiempo faltante sin producir extras negativas ni descuentos automáticos.

Este cuadro es una comprobación de las marcaciones y no reemplaza los valores guardados ni aprueba la jornada. Las primeras dos horas del saldo positivo se muestran al 25 % y el exceso al 35 %. Las nocturnas cuentan los tramos trabajados dentro de 22:00–06:00, incluso al cruzar medianoche. Feriado o descanso, descuentos y compensaciones muestran los ajustes aprobados; no se calculan importes monetarios.

- Los ajustes aprobados se suman al concepto elegido sin sobrescribir la cifra original.
- Descuentos y compensaciones se muestran aparte. No calculan dinero ni restan automáticamente de otro concepto.
- No sume nocturnidad y extras como tiempos independientes: pueden coincidir.
- Tiempo pendiente compara ocho horas efectivas con el trabajo reconstruido; no genera un descuento automático.
- El cambio de marcas, incidencias, ajustes o datos de una jornada aprobada exige una nueva revisión.
- Los bloques nocturnos usan fecha y hora completas. Cuando la salida se infiere al día siguiente por sus horas guardadas, se muestra un aviso para confirmarlo.
- Se muestran avisos cuando hay fechas futuras en los registros existentes. Esos datos no se borran ni se corrigen automáticamente.

## Huellero e importación

Abrir el dashboard solo consulta registros guardados. Ya no genera marcaciones simuladas. **Consultar conexión del equipo** comprueba conectividad de red; el cliente existente todavía no implementa la descarga física de registros y la pantalla lo indica. La marca web se identifica como Kiosko/DNI, sin atribuirle biometría o coordenadas ficticias.

El importador utiliza la sesión del usuario actual y reconoce las hojas tabulares por sede. Lee los encabezados por su nombre, conserva los códigos biométricos como texto y guarda la fecha con la zona horaria de Lima. Las hojas individuales y los resúmenes contables no se interpretan como nuevas fuentes de marcaciones.

Cada identidad se guarda con sede, equipo, código y nombre; puede existir sin cuenta de acceso. Un código corto como 2 no se convierte en DNI. La tabla **Códigos del huellero y trabajadores**, en Importador Excel, permite consultar las marcas y asociar el código a una **ficha de trabajador**, separada de las cuentas de acceso.

En **Identificar trabajador**, busque por nombre o apellido, DNI o código. También se reconocen los códigos de huellero que ya estén asociados a fichas. Seleccione el resultado y pulse **Confirmar trabajador**. La búsqueda muestra nombre completo, DNI, código de trabajador y área, sin repetir la sede de la fila.

Si no hay coincidencias, pulse **Registrar trabajador**. La ventana solicita nombres y apellidos completos, DNI de ocho dígitos y área. **Guardar y vincular** crea la ficha y su asociación dentro de una misma operación; no crea una cuenta de acceso. El código se toma exclusivamente de la identidad importada del Excel; no se genera un código adicional. La sede y el equipo siguen asociados a esa identidad. Un mismo código en otra sede o equipo puede identificar a una persona diferente. Las ventanas modales se centran en la pantalla. Se rechazan documentos duplicados y asociaciones contradictorias; los periodos cerrados siguen protegidos. Se registra quién realizó la vinculación. Las marcaciones originales no se sobrescriben.

Los usuarios existentes conservan sus cuentas y tienen una ficha de personal vinculada por DNI. Cuando no existe un dato fiable del área, aparece **Por completar**; no se confunde el rol de acceso con el área de trabajo. Las nuevas fichas se pueden mantener desde **Administración → Trabajadores**. La identificación por ficha no genera ni aprueba automáticamente jornadas u horas; Asistencia y HH.EE. admite fichas de trabajadores sin cuenta de acceso, además de los registros históricos por usuario.

La carga conserva todas las filas de procedencia. Una marca repetida no se vuelve a crear, aunque se guarda su nueva fila de origen. Las lecturas con código de ocho dígitos, mismo equipo, fecha, estado y verificación que se copiaron entre hojas se conservan como un evento con varias procedencias; los códigos cortos se delimitan por sede y equipo. El resultado distingue filas leídas, marcas nuevas, repetidas y códigos pendientes de cuenta.

Las marcas sin tipo inequívoco se guardan como **Por clasificar**. Valores como M/Ent se conservan literalmente sin asumir que todas las marcas son entradas. La importación no inventa horas trabajadas, refrigerios ni vueltas. Las jornadas nuevas vinculadas a usuarios quedan pendientes de revisión con tiempos por conciliar.

La carga se valida antes de guardar. Si falla una fila o hay un periodo cerrado, se revierte la operación. Una recarga del mismo archivo no duplica las marcas importadas con esta versión. Los datos históricos del importador anterior se conservan para revisión; no se borran ni se mezclan automáticamente con los nuevos.

## Validación y datos

La instancia que se abre en `localhost:8000` utiliza Docker y PostgreSQL. Las migraciones y cargas deben ejecutarse en ese servicio, por ejemplo `docker compose exec -T web python manage.py migrate --noinput`. Actualizar la base SQLite desde Windows no actualiza PostgreSQL. La recarga del código del servidor de desarrollo tampoco aplica migraciones automáticamente.

Se respaldó PostgreSQL antes de aplicar la migración 0006 y se cargó allí el archivo separado de marcaciones: lote 1, 4.287 filas de origen, 4.112 marcas únicas y 175 repeticiones. Se conservaron las siete marcas que ya existían en esa base. Las 39 pruebas también pasaron dentro de Docker con una base de prueba de PostgreSQL separada.

La actualización añade tablas de incidencias, ajustes, correcciones, historial y cierres, y campos de revisión al resumen diario. Se conserva el indicador de verificación anterior. La base local se respaldó antes de aplicar las migraciones; no se eliminaron jornadas ni marcaciones existentes.

Pasaron 24 pruebas automatizadas de permisos, filtros, plantillas, tramos, medianoche, revisión, ajustes, incidencias, exportación y cierre. Las pruebas crean una base separada. La renderización con registros existentes se comprobó desde Django. El navegador integrado confirmó que el servidor responde y solicita inicio de sesión; la comprobación visual del panel protegido queda pendiente. El primer intento con el servidor temporal de vista previa agotó el tiempo de espera.


## Corregir una ficha con DNI equivocado

En **Ver identificación → Editar trabajador**, si el DNI corregido ya tiene una ficha, se muestran nombre, DNI y área de la ficha encontrada. **Usar ficha existente y corregir vínculo** requiere una confirmación explícita: conserva los datos de destino, traslada todas las identidades de la ficha equivocada, mantiene los códigos originales y sus marcaciones y retira la ficha duplicada. El historial conserva ambas identificaciones y quién hizo la corrección. No se unen fichas solo por coincidencia de nombres; dos personas pueden llamarse igual.

Se protegen los periodos cerrados y las asociaciones contradictorias. Una ficha de origen con cuenta de acceso no se fusiona desde esta ventana, para evitar unir cuentas de personas diferentes. Cambiar el DNI en el formulario obliga a comprobar nuevamente la ficha encontrada. No se modifica ninguna ficha existente hasta confirmar la corrección.


## Enviar las marcaciones identificadas a Asistencia y HH.EE.

En Importador Excel, los filtros de sede, código y nombre delimitan los trabajadores del bloque **Pasar marcaciones a Asistencia y HH.EE.**. Seleccione Desde/Hasta (se proponen las fechas de las marcas importadas), confirme que revisó las fichas y pulse **Validar y pasar a Asistencia y HH.EE.**. Se exige nombre completo, DNI de ocho dígitos y área completada. Los códigos sin ficha quedan en el importador; no se crean cuentas de acceso. Las marcas originales y los códigos se conservan.

El envío genera jornadas pendientes por trabajador y fecha; repetirlo no duplica ni sobrescribe las jornadas existentes. Se abre Asistencia con el periodo enviado. La transacción se cancela si hay una ficha incompleta, una asociación contradictoria o un periodo cerrado. Las entradas/salidas nocturnas ya clasificadas conservan el cruce de fecha; las marcas sin clasificar se presentan por fecha calendario para revisión, sin inferir refrigerios ni cruces nocturnos. Revise esos casos en el detalle.

Se reconstruyen tiempos solo con secuencias completas. Las extras se calculan sobre ocho horas efectivas; el turno se utiliza para comprobar el horario y la tardanza. En caso contrario, los cálculos quedan pendientes: se pueden corregir los eventos y asignar el turno desde el detalle, y conciliar los valores guardados mediante ajustes. Enviar no aprueba las jornadas ni cierra el periodo. Los nuevos registros tienen estado **Por revisar marcaciones** para no afirmar asistencia o tardanza sin validación.


## Asistencia por trabajador y clasificación del periodo

La tabla principal muestra una fila por trabajador con nombre, DNI, códigos importados, área, sede, cantidad de jornadas y estado de revisión. Los filtros siguen delimitando el periodo consultado. **Revisar marcaciones** abre una ventana centrada con todas las marcas incluidas en las jornadas de esa persona durante el periodo, ordenadas por fecha y hora.

En la ventana se clasifica cada marca como entrada, salida a refrigerio, retorno o salida final. Se puede conservar el horario individual de cada jornada o asignar uno a las jornadas abiertas. La clasificación laboral no solicita un motivo; el sistema registra automáticamente la acción, su responsable y la fecha. **Guardar clasificación y validar jornadas** conserva el evento original y guarda las correcciones aparte. Se comprueba la secuencia de cada día y se recalculan los tiempos completos; las extras usan una base fija de ocho horas efectivas. Los ajustes existentes no se sobrescriben: deben conciliarse desde el detalle. La aprobación contable sigue siendo un paso independiente.

El resultado por jornada muestra trabajo, refrigerio, extras y avisos, con acceso al detalle, incidencias, ajustes e historial. Las marcas de periodos cerrados son de solo lectura. Los cambios ajenos al trabajador o realizados sobre una revisión desactualizada cancelan la operación sin guardar cambios parciales. La consulta queda restringida por los permisos del usuario.


## Fechas sin marcaciones

El resultado por jornada incluye todas las fechas Desde/Hasta, incluso si no existe una jornada guardada. Consultar no crea jornadas ni faltas. Los días vacíos aparecen como **Sin marcaciones**, sin asumir que fueron feriados o descansos.

**Registrar situación** permite indicar feriado no laborado, descanso semanal, día no trabajado pendiente de justificar, vacaciones, permiso o descanso médico. Se guarda una jornada pendiente y una incidencia de día completo; no se generan marcas, horas ni descuentos. El detalle permite revisar y aprobar la incidencia. Los feriados y descansos aprobados se muestran como días justificados. Las fechas con marcas o jornadas existentes se revisan desde su detalle; los periodos cerrados no se modifican.


## Situación del día sin detalle de marcaciones

Los días sin marcas con una situación de día completo registrada (descanso semanal, feriado no laborado, vacaciones, permiso o descanso médico) muestran su descripción y **No laboró** en trabajo, refrigerio y extras, incluso si la aprobación está pendiente. No se exige turno ni entrada/salida para representar esa situación. Registrar no equivale a aprobar.

En la misma fila, Contabilidad o Gerencia puede usar **Aprobar situación** y después **Aprobar día**. El detalle de marcaciones no se abre para estos días; los enlaces antiguos vuelven a la ventana del trabajador. Los días sin clasificación siguen como **Sin marcaciones → Registrar situación**. Las jornadas que sí tienen marcas o ajustes conservan el detalle para no ocultar información pendiente.


## Completar una marcación faltante de forma manual

En el detalle de una jornada, debajo del cuadro del Excel, **Agregar marcación manual** solicita fecha, hora confirmada, tipo de evento, código/equipo del trabajador, motivo y referencia opcional. **Guardar marcación manual y validar** conserva los tipos seleccionados en el cuadro y registra la marca nueva en una misma transacción. Si falta información, hay un conflicto o la fecha está cerrada, no se guardan cambios parciales.

La nueva marca se identifica como **Registro manual en el sistema**, con responsable, fecha de registro, motivo y evidencia opcional. No se le atribuye verificación por huella ni un lote Excel. Las filas originales del huellero no se alteran. La secuencia y los tiempos se reconstruyen con la nueva marca; el día queda pendiente de aprobación contable. Las jornadas con ajustes previos se concilian desde el detalle.

La hora no se genera automáticamente ni se copia de una captura. Debe confirmarse antes de registrarla. Se rechazan marcas repetidas, futuras, de otro código/persona o fuera de la jornada; se admite la fecha siguiente para un cruce de medianoche que no invada otra jornada ni produzca un intervalo de 24 horas o más. Los registros del Excel conservan sus segundos originales; una hora manual introducida solo con minutos usa los segundos cero indicados por el formulario.


## Avance de validación y aprobación conjunta

La lista principal separa **Validación** de **Aprobación contable**. Un día se cuenta como validado si sus marcas forman una secuencia completa o si su situación no laborada está aprobada. El indicador se reconstruye con las fuentes actuales; no depende solamente del estado guardado ni supone una aprobación contable.

En la ventana del trabajador, **Aprobar todas las jornadas listas** requiere confirmar la revisión del periodo. Solo Contabilidad, Gerencia o un superusuario puede utilizarlo. Se vuelven a comprobar las jornadas en el servidor: se aprueban las completas sin bloqueos y se conservan pendientes las incompletas, observadas, cerradas o con incidencias/ajustes pendientes. Un descanso con situación aprobada también puede aprobarse en conjunto. No se aprueban incidencias ni se fabrican jornadas para fechas vacías.

El resultado de la última operación enumera las fechas no aprobadas y sus motivos, incluidas las fechas sin una situación registrada. Repetir el envío no duplica la aprobación ni el historial de los días ya aprobados. Se conserva el responsable y la fecha de cada aprobación; el periodo no se cierra automáticamente.
