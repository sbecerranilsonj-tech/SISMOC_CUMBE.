# Análisis de SISMOC-CUMBE y su relación con las prácticas preprofesionales

Fecha de revisión: 16 de octubre de 2026.

## 1. Diagnóstico

SISMOC-CUMBE tiene una finalidad pertinente para el área contable de Transportes El Cumbe: reducir el trabajo manual con asistencia y conciliación. Existe una base de software concreta en Django, pero el estado observado corresponde a un prototipo del primer sprint. La importación real presenta problemas de integridad y la consulta de asistencia mezcla simulación con registros persistentes. Deben resolverse antes de usar los resultados para decisiones de personal o cierres contables.

El principal paso siguiente es terminar y validar un flujo completo de asistencia con los archivos de la empresa, y después incorporar conciliación. El alcance adicional de ventas, QR, GPS, encomiendas y aplicaciones móviles requiere priorización y una estrategia de integración con el sistema existente.

## 2. Alcance de la revisión y límites

- Lectura del código propio, modelos, migraciones, API, interfaz, configuración Docker, dependencias y script de pruebas.
- Consulta de SQLite en modo de solo lectura. No se modificaron registros, credenciales ni código funcional.
- Extracción de texto de sílabo, reglamento, guías y rúbricas, cartas y documentos académicos accesibles.
- Inspección del XML de los tres libros XLSX/XLSM operativos, sus hojas, muestras de celdas y errores almacenados. No se recalcularon ni modificaron libros.
- Extracción de texto de los DOCX de trabajos anteriores para reconocer antecedentes, sin validar visualmente sus diagramas ni asumir vigencia de sus afirmaciones.
- Inventario del XLS de itinerarios: es un archivo binario antiguo; su contenido no fue analizado. Tampoco se transcribieron las dos grabaciones de reuniones.
- Dos PDF denominados CAP y CCP no ofrecen texto útil en la extracción y requieren revisión visual/OCR. No se verificaron firmas ni la autenticidad de los documentos.
- Validación sintáctica mediante AST de los archivos Python revisados: correcta. No equivale a comprobar funcionamiento.
- No se ejecutó el script de integración: el entorno virtual depende de un ejecutable Python 3.12 que no está accesible desde esta sesión. Además, el script escribe en la base configurada y consulta la red del huellero. El Python 3.14 accesible no tiene Django instalado.
- No se hizo una auditoría normativa externa ni una certificación de cumplimiento. Las referencias normativas del plan se trataron como requisitos por verificar.

## 3. Contexto académico y documental

El sílabo 2026-II corresponde al curso 1IS101, ciclo X, 8 créditos y 16 semanas. Establece:

| Evidencia | Momento indicado | Peso |
|---|---|---|
| Plan de prácticas | Semana 3 | 20% |
| IQ01 | Semana 7 | 10% |
| IQ02 | Semana 12 | 10% |
| IQ03 | Semanas 13–14 | 5% |
| Exposición de IQ03 | Semanas 13–14 | 5% |
| Supervisión | Semanas 9–11 | 20% |
| Trabajo final | Semana 16 | 10% |
| Sustentación final | Semana 16 | 15% |
| Actitud | Evaluación del curso | 5% |

IQ03 incluye un proyecto de innovación con modelo de negocio de una empresa de base tecnológica relacionada con el sector. No basta con presentar otro avance de programación. IQ02 también pide el certificado del taller de CV mencionado en el sílabo.

La carta universitaria dirigida a El Cumbe solicita un mínimo de 450 horas. La carta de aceptación ubica al estudiante Nilson Jesus Silupu Becerra en contabilidad, con supervisión de CPC. Yaneli Terrones Vásquez, desde el 23/09/2026 hasta el 16/12/2026.

### Inconsistencias que deben resolverse

1. **RUC:** la carta de aceptación consigna `20105752149`; el plan, README y código usan `20480397731`. Esta revisión no determina cuál es correcto. Contrastar con la ficha RUC y el documento aprobado de la empresa antes de unificar.
2. **Período:** el plan señala 22/09–15/12; la aceptación señala 23/09–16/12.
3. **Cronograma:** la tabla del plan lleva el cierre al 28/12 y un sprint al 21/12, después del término indicado en la aceptación. Su Gantt usa fechas distintas de la tabla, incluso para Sprint 1.
4. **Informes:** el plan asocia IQ01 a semanas 4–5 e IQ02 a semanas 8–9; el sílabo los sitúa en semanas 7 y 12. Separar el calendario interno de desarrollo del calendario académico.
5. **Identidad y supervisor:** persisten campos de nombres, contacto y supervisor sin completar, aunque otras secciones declaran aprobación de una persona concreta.
6. **Tecnologías:** el acta propuesta promete Next.js/PWA; el repositorio contiene una plantilla Django HTML. El README menciona varias versiones de Django, mientras requirements fija `>=5.1,<5.2`. Actualizar según la decisión técnica y el entorno realmente instalado.
7. **Controles declarados:** el plan afirma bcrypt, copias automatizadas y cumplimiento total. El código revisado no configura bcrypt ni aporta un mecanismo de respaldo automatizado. La lista de cotejo menciona 6 roles y el sistema define 7.
8. **Metas:** reducir el tiempo 85%, error 0% y cumplimiento 100% aparecen sin medición de referencia. Presentarlos como objetivos y definir cómo se comprobarán.
9. **Documentos de otros contextos:** hay una carta dirigida a la Municipalidad Provincial de Lambayeque. Evitar mezclarla con el expediente de El Cumbe. Algunas guías son de 2026-I: contrastar fechas con el sílabo vigente.

No se debe equiparar un texto que declara conformidad con un acta efectivamente firmada. Verificar las evidencias de aprobación antes de afirmarlas en informes.

## 4. Información operativa de la empresa

| Fuente | Estructura observada | Consecuencia para el proyecto |
|---|---|---|
| ASISTENCIA AGOSTO 2026.xlsx | 51 hojas; incluye personas, agencias y consolidaciones | Requiere identificar tipos de hoja y evitar importar resúmenes como marcaciones |
| CONCILIACION BCP SOLES JULIO 2026.xlsx | 33 hojas: Movimientos Históricos, BANCOO y 31 hojas diarias | Requiere distinguir banco, registros diarios y posibles datos repetidos |
| DESCANSO CHOFERES 08.2026.xlsm | 8 hojas mensuales de enero a agosto, con nombres, días, horarios y códigos | Es una matriz de control, distinta de un log tabular de biometría |
| Estado de cuenta BCP julio | 127 páginas con texto extraíble | Es una fuente posible de contraste; no se verificaron saldos ni importes en este análisis |

El libro de asistencia conserva 11 celdas con error `#REF!`, todas en la parte XML `sheet22.xml`, columna J. Son resultados guardados por Excel, no un recálculo de esta revisión. No usar esas fórmulas como referencia única para validar el nuevo cálculo.

El libro de descansos contiene códigos X, horarios, permisos y totales que incluyen medias vueltas. Debe confirmarse su significado con contabilidad. El supuesto del código de que X siempre vale una vuelta y XX siempre dos no queda demostrado por la estructura del libro. No convertir presencia en tiempo de conducción sin datos operativos que lo respalden.

Los trabajos anteriores aportan mapas de procesos, análisis de arquitectura y prototipos de ventas/encomiendas. Son antecedentes académicos aprovechables con atribución, pero no prueban que exista una integración operativa autorizada o que todos sus diagnósticos sigan vigentes. Hay diferencias de dirección y formulación de misión entre antecedentes y plan: confirmar la información institucional.

## 5. Arquitectura y cobertura actual

La separación en `core`, `asistencia`, esquemas y servicios es razonable para este tamaño. Django aporta usuarios, ORM, migraciones y administración. Ninja organiza los endpoints y la documentación de API. SQLite sirve al prototipo; Docker contempla PostgreSQL.

| Función | Evidencia actual | Evaluación |
|---|---|---|
| Usuarios y 7 roles | Modelo personalizado, login JWT y endpoints de administración | Implementación base; necesita cerrar brechas de acceso |
| Importación de asistencia | Parser y registro de carga | Implementada parcialmente; problemas confirmados en datos existentes |
| Resumen y reporte de horas | Modelo diario y endpoints | Requiere corregir reglas y período de consulta |
| Conexión ZKTeco | Prueba de socket; bloque de descarga con `pass` | Descarga real pendiente |
| Marcación móvil | Endpoint recibe DNI y coordenadas | No demuestra reconocimiento facial ni geofencing |
| Conciliación bancaria | Sin módulo ni router específico | Pendiente |
| Itinerarios y bloqueo por descanso | Sin modelos y servicio de asignación | Pendiente |
| Croquis, QR y validación offline | Sin implementación funcional correspondiente | Pendiente |
| GPS, rendiciones, encomiendas y manifiesto | Descritos en el plan y roles | Pendientes |

La interfaz describe funciones futuras. La descripción de un rol, un campo GPS o una dependencia instalada no demuestra que la función esté implementada.

## 6. Hallazgos técnicos prioritarios

### P0: integridad de la asistencia

**Simulación persistente al consultar.** `asistencia/services/zkteco_live.py` crea entradas para todos los usuarios activos si no hay marcaciones del día. Las guarda con origen ZKTeco. La descarga de hardware está vacía y el dispositivo desconectado se presenta como `ACTIVO (ONLINE)`. `core/views.py` invoca este servicio al abrir el dashboard; también lo hace un GET público. Corregir antes de cualquier piloto: consulta sin escritura, desconexión explícita y datos de demostración en entorno separado.

**La base ya contiene resultados anómalos.** En lectura de SQLite se encontraron:

- 50 usuarios: 43 administrativos y 7 distribuidos entre los demás roles.
- 42 usuarios con DNI provisional iniciado en TEMP.
- 11 755 marcaciones y 1 153 resúmenes diarios.
- Rango de resúmenes desde `2026-07-27` hasta `7546-10-10`.
- Una carga del archivo real de agosto marcada COMPLETADO, con 14 538 filas y 49 empleados identificados, registrada como período `2026-10`.

Estos números describen el estado almacenado, no trabajadores o asistencias reales validados. Los datos están mezclados con registros de demostración. No borrarlos ni corregirlos masivamente sin conservar copia, identificar procedencia y acordar el resultado esperado.

**Parser demasiado permisivo.** En las hojas individuales convierte cada celda a fecha y solo exige año >=2024. No restringe la lectura a la columna de marcación, no verifica mes esperado y no extrae el DNI desde el cuerpo de esas hojas. Intenta asociar personas por una parte del nombre y crea usuarios TEMP si no encuentra coincidencia. Esto es coherente con los problemas observados, aunque no se trazó cada fecha anómala hasta su celda de origen.

Solución propuesta: contrato por formato, clasificación de hojas, lectura explícita de columnas, fecha dentro del período elegido, DNI/ID biométrico como vínculo estable y una bandeja para identidades no resueltas. Previsualizar errores antes de confirmar una carga atómica.

### P0: acceso y credenciales

- `POST /api/asistencia/marcar` usa `auth=None`: permite declarar asistencia por DNI y acepta coordenadas sin verificación de identidad ni ubicación.
- `GET /api/asistencia/tiempo-real` es público y expone datos de personal, además de poder crear las marcaciones descritas.
- La plantilla inicia sesión automáticamente con credenciales incrustadas de contabilidad para subir Excel. Cualquier persona que recibe ese HTML puede leerlas.
- `/resumen` restringe a conductor, administrativo y operador, pero omite boletería: este rol puede consultar resúmenes ajenos.
- `AuthBearer` comprueba `esta_activo`, pero no `is_active`. Conviene unificar el estado o comprobar ambos.
- Docker Compose incluye secretos literales, DEBUG habilitado y hosts abiertos. `.dockerignore` no excluye `.env`, y el Dockerfile copia el contexto completo.

Reemplazar el acceso automático por una sesión real, definir permisos por operación, exigir identidad o autenticación de dispositivo y separar configuración de desarrollo y despliegue. Rotar credenciales compartidas si se usaron fuera del entorno de prueba.

### P1: cálculo y trazabilidad

- El parser agrupa por fecha calendario, por lo que no reconstruye correctamente una jornada que cruza medianoche.
- Solo calcula nocturnidad cuando la última hora es >=22:00. Un intervalo 00:00–06:00 no se contabiliza y un turno 22:00–06:00 se divide entre días.
- Descuenta una hora fija si la jornada supera seis horas, sin emparejar salida y retorno de refrigerio.
- Aplica un turno administrativo general; no hay asignación efectiva de turno por trabajador/fecha.
- Infiere vueltas a partir de la separación entre marcaciones y asigna ocho horas a cualquier conductor con vueltas. Es una heurística que requiere validación con la empresa.
- El registro manual actualiza primera/última hora, sin recalcular el conjunto de horas con el mismo motor del importador.
- La transacción cubre la auditoría, después de procesar datos: una falla previa puede dejar importación parcial.
- La auditoría usa el mes de ejecución y no conserva el archivo mediante su FileField. Faltan hash, ubicación original y referencia de fila/hoja por registro.
- `mes_periodo` en el reporte cambia la etiqueta, pero no define el filtro de fechas. Puede mostrar un período distinto del consultado.
- El endpoint acepta CSV pero el parser usa ExcelFile/read_excel; se anuncia XLS sin declarar xlrd como dependencia. La extensión aceptada debe corresponder al lector disponible.
- Faltan validaciones de catálogo para rol, origen y evento, y tratamiento controlado de conflictos de unicidad al actualizar usuarios.
- La lista de presentes usa el último evento por persona, pero lo presenta como primera marcación y declara PRESENTE incluso ante una salida.

### P1: pruebas

`test_sprint1_api.py` es un script manual con datos y credenciales concretos, no una suite aislada de Django TestCase. Usa la base configurada. Sus comprobaciones se centran en respuestas 200 y varias validaciones son condicionales: pueden no ejecutarse si falta el registro buscado. Incluso prueba como éxito que se pueda marcar sin autenticación.

Crear pruebas aisladas con: archivo real anonimizado y resultados revisados, 22:00–06:00, refrigerio registrado, marca incompleta, persona desconocida, carga repetida, fecha fuera de período, denegación de acceso, desconexión del reloj y consistencia entre importación y marcación manual. No ejecutar la integración contra la base de trabajo.

## 7. Recomendación de alcance

Priorizar un MVP de **asistencia y conciliación para contabilidad**, con autenticación, auditoría y reportes. Mantener Django y una interfaz sencilla es suficiente si permite completar y validar los procesos. Añadir Next.js no resuelve los problemas de calidad del importador.

Orden propuesto:

1. Corregir información institucional, fechas y calendario. Precisar objetivos y criterios de aceptación con la supervisora.
2. Cerrar acceso público indebido, eliminar simulación automática del flujo real y conservar una copia de la base actual.
3. Construir importación validada del formato real de asistencia y reconciliar registros con el padrón.
4. Unificar cálculo de jornadas, refrigerios y turnos, con revisión de contabilidad y muestras esperadas.
5. Implementar conciliación bancaria: primero importar y normalizar, luego proponer coincidencias por referencia/fecha/importe, gestionar ambigüedades y confirmar con revisión humana.
6. Completar evidencias, manuales, respaldo y prueba de restauración antes del piloto.
7. Considerar itinerarios, QR y móvil según tiempo disponible y acuerdos de integración. Si el alcance ya fue aprobado, documentar cualquier cambio y su conformidad.

El plan describe un sistema de ventas heredado sin acceso al código o base. Antes de desarrollar croquis y QR, definir de dónde llegan boletos, asientos, rutas y anulaciones. Usar exportaciones autorizadas o una interfaz acordada y comprobar cómo se evitan ventas duplicadas y datos desactualizados.

## 8. Evidencias académicas que conviene preparar

Para IQ01, la guía pide actividades del centro externas al proyecto, visión del producto, requisitos F/NF, selección justificada de tecnologías, backlog Como/Quiero/Para, tareas, objetivo del sprint, historias con aceptación, Kanban pendiente/terminado, incremento y Sprint Review con feedback del supervisor. Incluye tres conclusiones, tres sugerencias, roadmap y rúbrica.

Para el informe final, la guía incluye ficha RUC, mapa de procesos estratégicos/apoyo/core, BPMN de procesos core y sus descripciones, resumen de Scrum con evidencias por sprint, situaciones problemáticas/resultados, lista de cotejo de datos, constancia de horas, conclusiones vinculadas a objetivos, al menos cinco recomendaciones e historias anexas.

Una matriz útil es: **problema → requisito → historia → implementación → prueba → evidencia → conformidad**. Ejemplo: procesamiento manual de asistencia → importar archivo de agosto → previsualizar y validar → parser específico → comparar muestra esperada → reporte de diferencias y acta de revisión.

Medir el tiempo del proceso actual y del piloto con el mismo volumen. Registrar filas válidas/rechazadas, personas identificadas sin ambigüedad, diferencias de horas por empleado y casos conciliados pendientes de revisión. No presentar cifras de ahorro como resultados hasta medirlas.

## 9. Fuentes locales principales

- `../Sílabo_PPP_2026-II_.pdf`, páginas 6–7.
- `../REGLAMENTO PRACTICAS PRE PROFESIONALES.pdf`.
- `../GUIAS/1 - Guía de producto - Plan de Prácticas.pdf` y su rúbrica.
- `../GUIAS/2 - Guía de producto - Primer informe quincenal IQ01.pdf`.
- `../GUIAS/3 - Guía de producto - Segundo informe quincenal IQ02.pdf`.
- `../GUIAS/4 - Guía de producto - Tercer informe quincenal IQ03.pdf`.
- `../GUIAS/5 - Guía de producto - Informe Final.pdf`.
- `../GUIAS/plan_de_practicas_el_cumbe.md`.
- `../DOCUMENTOS/CARTA DE ACEPTACIÓN DE PRÁCTICAS PRE-PROFESIONALES.pdf`.
- `../DOCUMENTOS/1000566570_202602_2003_154141215 (1).pdf`.
- Libros operativos de `../CENTRO PRACTICAS/` y antecedentes de `../TRABAJOS _ANTERIORES/`.
- Código y SQLite del repositorio, leídos sin ejecutar operaciones de negocio.

Los extractos auxiliares están en `tmp/analisis_fuentes/`. Contienen información interna: mantenerlos locales y fuera de entregas públicas o commits. Este informe no reproduce DNI individuales, movimientos bancarios ni contraseñas.
