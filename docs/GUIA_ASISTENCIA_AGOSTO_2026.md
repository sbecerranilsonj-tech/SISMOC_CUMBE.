# Guía de lectura de la asistencia de agosto de 2026

Revisión para continuar SISMOC-CUMBE. Fecha de análisis: 16/10/2026.

## Qué contiene y qué se revisó

Se leyeron las 51 hojas y sus celdas, fórmulas y resultados guardados: 6 fuentes por sede, 43 controles individuales, una hoja de notas y un resumen contable. Hay 7.023 fórmulas. Las fuentes reúnen 4.287 marcaciones fechadas, antes de conciliar personas y sedes. El archivo original no se modificó ni se recalculó. Los resultados guardados pueden diferir de una futura recalculación de Excel. No se hizo una revisión visual de impresión.

Archivo fuente: `../CENTRO PRACTICAS/ASISTENCIA AGOSTO 2026.xlsx`.

La lectura emitió una advertencia sobre un encabezado o pie de página no interpretable. Las celdas se pudieron extraer.

## Cómo seguir el proceso

El flujo de negocio que refleja el archivo es: marcaciones por sede → selección y revisión por trabajador → cálculo de tiempos e incidencias → transcripción al CUADRO → revisión contable.

Es un flujo conceptual. No se encontraron fórmulas con referencias válidas entre hojas. Por ello, cambiar una marcación de una sede no actualiza automáticamente el control individual ni el CUADRO.

Las seis fuentes tienen columnas Departamento, Nombre, No., Fecha/Hora, equipo y verificación. CAJAMARCA incorpora además Estado. No. puede contener un DNI o un identificador interno corto del reloj. No debe convertirse automáticamente en DNI rellenándolo con ceros. FP y FACE son valores de verificación, no tipos de entrada o salida. Las otras fuentes no aportan una columna explícita de tipo de evento.

## Cómo leer una hoja individual

En muchas hojas la columna C contiene el identificador y D la fecha y hora. E resta marcas consecutivas. F contiene REFRIGERIO o una duración base. G calcula trabajo menos base. H separa las primeras dos horas de exceso, I el exceso posterior, J calcula nocturnidad y K recoge feriado o descanso. MIDORI, CELESTE y GRECIA usan columnas desplazadas: reconocer contenido y fórmulas, no fijar letras para todas las hojas.

Esta estructura tiene excepciones: G no siempre significa horas extras, las bases no son uniformes, existen jornadas de dos, cuatro o más marcas y algunos resultados se sustituyeron por números o texto.

### Ejemplo completo: EMIR MONTEZA, celdas D3:J6

El 30/07 registra 03:25:17, 07:47:08, 08:32:10 y 15:05:14. El archivo interpreta los extremos del intervalo central como salida y retorno de refrigerio.

- Primer tramo: 4 h 21 min 51 s.
- Refrigerio observado: 45 min 02 s.
- Segundo tramo: 6 h 33 min 04 s.
- Trabajo efectivo: 10 h 54 min 55 s.
- Base en F6: 8 h. Exceso G6: 2 h 54 min 55 s.
- H6: 2 h en la categoría 25 %. I6: 54 min 55 s en la categoría 35 %.
- J6: 2 h 34 min 43 s antes de las 06:00.

Restar una hora fija de refrigerio produciría 10 h 39 min 57 s, una diferencia de 14 min 58 s respecto del cálculo por tramos. Es un ejemplo histórico de julio incluido en este libro.

### Ejemplo de medianoche: ALEJANDRO ARTEAGA, D3:I4

Entra el 30/07 a las 19:56:57 y sale el 31/07 a las 07:36:31. El intervalo es 11 h 39 min 34 s; F4 usa 8 h 45 min y G4 devuelve 2 h 54 min 34 s. Agrupar solo por fecha calendario separaría entrada y salida. La base de 8 h 45 min debe confirmarse como regla operativa antes de automatizarla.

### Unidades que hay que distinguir

Una duración de Excel es una fracción de día. Para convertirla a horas decimales se multiplica por 24. En CUADRO se usan horas decimales: 30/60 = 0,5 h y 2+30/60 = 2,5 h. En cambio, ISRAEL ROQUE!J12 contiene el número 8 en una columna donde otras filas son duraciones. ROJAS ALAN!J110 contiene 2,3. No asumir que todos estos valores tienen la misma unidad o que 2,3 significa 2 h 30 min.

Las etiquetas 25 %, 35 % y 22:00–06:00 se describen como categorías presentes en el archivo. Esta revisión no verifica normas legales ni calcula pagos en soles.

## Recorrido hoja por hoja, en el orden original

En cada control se cuenta cada celda con fecha y hora como una marca, no como una jornada. Las notas se transcriben para localizar evidencia; algunas tienen errores de ortografía o contradicen el calendario.

### 01. CHICLAYO

**Función:** fuente de marcaciones de la sede. Contiene 2.010 registros fechados. entre 2026-07-27 y 2026-08-28. No tiene fórmulas.

**En el sistema:** importar como eventos originales con sede, equipo, identificador local, fecha y hora. Conservar fila de origen y resolver identidad antes de calcular jornadas.

### 02. ALEJANDRO ARTEAGA

**Función:** control individual. Tiene 96 marcas entre 2026-07-30 y 2026-08-28, y 146 fórmulas.

**Qué enseña para SISMOC:** Jornadas que cruzan medianoche; aparecen bases de 8 h y de 8 h 45 min. Conservar fecha y hora completas y definir la fecha laboral.

**Evidencia y anotaciones:**

- C1: DESCANSO SABADOS.
- C7: 01 DESCANSO.
- A22: FERIADO.
- C32: 08 DESCANSO.
- C57: 15 DESCANSO.
- C82: 22 DESCANSO.

### 03. BRUNELLA HUAMAN

**Función:** control individual. Tiene 96 marcas entre 2026-07-30 y 2026-08-27, y 163 fórmulas.

**Qué enseña para SISMOC:** Descuentos por horas y minutos. Registrar cada ajuste con motivo, duración y aprobación.

**Evidencia y anotaciones:**

- C1: DESCANSO VIERNES.
- C7: 31 DESCANSO.
- A28: FERIADO.
- C32: 07 DESCANSO.
- H44: DESCUENTO 3HRS.
- H56: DESCUENTO 15 MIN.
- C57: 14 DESCANSO.
- H65: DESCUENTO 10 MIN.
- H69: DESCUENTO 10 MIN.
- H73: DESCUENTO 10 MIN.
- C82: 21 DESCANSO.
- H86: DESCUENTO 20 MIN.
- H90: DESCUENTO 15 MIN.
- H94: DESCUENTO 10 MIN.
- C95: 25 NO TRABAJÓ.
- H95: DESCUENTO 1 DÍA.
- D105: DESCUENTO 4 HRS Y 30 MIN.
- D106: 4 HRS.
- D107: 30 MIN.

### 04. CARLOS ARTEAGA

**Función:** control individual. Tiene 100 marcas entre 2026-07-30 y 2026-08-27, y 172 fórmulas.

**Qué enseña para SISMOC:** Descuentos y compensaciones entre fechas. Vincular el tiempo compensado al día de origen.

**Evidencia y anotaciones:**

- C1: DESCANSO LUNES.
- C19: 03 DESCANSO.
- A28: FERIADO.
- C44: 10 DESCANSO.
- C69: 17 DESCANSO.
- H73: DESCUENTO 45 MIN.
- H77: COMPENSAR 18/08.
- H80: COMPENSAR 18/08.
- C94: 24 DESCANSO.

### 05. DAYANA RAMOS

**Función:** control individual. Tiene 104 marcas entre 2026-07-30 y 2026-08-27, y 182 fórmulas.

**Qué enseña para SISMOC:** Trabajo durante descanso y feriado. Separar asistencia, calendario y tratamiento contable.

**Evidencia y anotaciones:**

- C1: DESCANSO VIERNES.
- A7: TRABAJÓ DESCANSO.
- C27: 05 DESCANSO.
- A28: FERIADO.
- C52: 12 DESCANSO.
- C85: 21 DESCANSO.

### 06. ELIZABETH BRIONES

**Función:** control individual. Tiene 100 marcas entre 2026-07-30 y 2026-08-27, y 175 fórmulas.

**Qué enseña para SISMOC:** Descanso semanal de martes y feriado. Su bloque del resumen usa un rango de suma distinto de la mayoría.

**Evidencia y anotaciones:**

- C1: DESCANSO MARTES.
- C23: 04 DESCANSO.
- A28: FERIADO.
- C48: 11 DESCANSO.
- C73: 18 DESCANSO.
- C98: 25 DESCANSO.

### 07. EMIR MONTEZA

**Función:** control individual. Tiene 100 marcas entre 2026-07-30 y 2026-08-27, y 175 fórmulas.

**Qué enseña para SISMOC:** Caso claro de cuatro marcaciones: trabajo, refrigerio y trabajo. Incluye horas antes de las 06:00.

**Evidencia y anotaciones:**

- C1: DESCANSO SABADOS.
- C11: 01 DESCANSO.
- A28: FERIADO.
- C36: 08 DESCANSO.
- C61: 15 DESCANSO.
- C86: 22 DESCANSO.

### 08. Hoja1

**Función:** notas técnicas. B3 menciona Python y B4 una biblioteca para leer Excel. No contiene asistencia ni fórmulas. **En el sistema:** excluir del importador.

### 09. JHON DAVILA

**Función:** control individual. Tiene 48 marcas entre 2026-07-30 y 2026-08-27, y 84 fórmulas.

**Qué enseña para SISMOC:** Vacaciones del 1 al 15 y descuentos. La ausencia de marcaciones durante vacaciones no debe convertirse en falta.

**Evidencia y anotaciones:**

- C1: DESCANSO MIERCOLES.
- C11: 01 - 15 VACACIONES.
- C24: 19 DESCANSO.
- H44: DESCUENTO 15 MIN.
- H48: DESCUENTO 10 MIN.
- C49: 26 DESCANSO.
- H53: DESCUENTO 10 MIN.
- D56: DESCUENTO 35 MIN.
- D57: 0 HRS.
- D58: 35 MIN.

### 10. JULIO CHUNG

**Función:** control individual. Tiene 94 marcas entre 2026-07-30 y 2026-08-27, y 167 fórmulas.

**Qué enseña para SISMOC:** Día no trabajado y entradas excepcionales con descuentos. Conservar la justificación y distinguir ausencia de jornada incompleta.

**Evidencia y anotaciones:**

- C1: DESCANSO MIERCOLES.
- C27: 05 DESCANSO.
- C44: 10 NO TRABAJÓ.
- H44: DESCUENTO 1 DÍA.
- C49: 12 DESCANSO.
- A50: ENTRÓ A ESA HORA.
- H51: DESCUENTO 2 HRS Y 20 MIN.
- C72: 19 DESCANSO.
- C97: 26 DESCANSO.
- D104: DESCUENTO 2 HRS Y 20 MIN.
- D105: 2 HRS.
- D106: 20 MIN.

### 11. ISRAEL ROQUE

**Función:** control individual. Tiene 54 marcas entre 2026-07-30 y 2026-08-28, y 106 fórmulas.

**Qué enseña para SISMOC:** Combina turnos diurnos y nocturnos. Hay valores nocturnos escritos como números, como J12=8, junto a duraciones de Excel.

**Evidencia y anotaciones:**

- C1: DESCANSO MARTES.
- A20: FERIADO.
- C21: 07 DESCANSO.
- C34: 14 DESCANSO.
- C47: 21 DESCANSO.

### 12. LILIAN VASQUEZ

**Función:** control individual. Tiene 90 marcas entre 2026-08-01 y 2026-08-27, y 155 fórmulas.

**Qué enseña para SISMOC:** Descuentos de distinta duración, con un resumen manual al final. Evitar contar dos veces el detalle y su total.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGOS.
- C7: 02 DESCANSO.
- A20: FERIADO.
- H31: DESCUENTO 20 MIN.
- C32: 09 DESCANSO.
- H42: DESCUENTO 2HRS Y 20 MIN.
- C55: 16 DESCANSO.
- H79: DESCUENTO 10 MIN.
- C80: 23 DESCANSO.
- H84: DESCUENTO 10 MIN.
- D98: DESCUENTO 3 HRS.
- D99: 3 HRS.
- D100: 0 MIN.

### 13. LILIANA HURTADO

**Función:** control individual. Tiene 96 marcas entre 2026-07-30 y 2026-08-27, y 168 fórmulas.

**Qué enseña para SISMOC:** Descanso por cumpleaños y cambios respecto del descanso anunciado. Necesita excepciones al calendario regular.

**Evidencia y anotaciones:**

- C1: DESCANSO SABADOS.
- C7: 31 CUMPLEAÑOS.
- C8: 01 DESCANSO.
- A25: FERIADO.
- C33: 08 DESCANSO.
- C62: 16 DESCANSO.
- C83: 22 DESCANSO.

### 14. MARIASOL SANCHEZ

**Función:** control individual. Tiene 92 marcas entre 2026-07-31 y 2026-08-27, y 154 fórmulas.

**Qué enseña para SISMOC:** Numerosos descuentos, compensaciones y un día no trabajado. No confundir déficit horario con horas extras negativas.

**Evidencia y anotaciones:**

- C1: DESCANSO MIERCOLES.
- C3: 30 DESCANSO.
- H15: DESCUENTO 1HR Y 15 MIN.
- H19: DESCUENTO 15 MIN.
- H23: DESCUENTO 45 MIN.
- C24: 05 DESCANSO.
- A25: FERIADO.
- H40: DESCUENTO 20 MIN.
- H48: DESCUENTO 20 MIN.
- C49: 12 DESCANSO.
- H57: DESCUENTO 1HR Y 15 MIN.
- C58: 15 NO TRABAJÓ.
- H58: DESCUENTO 1 DÍA.
- H62: DESCUENTO 15 MIN.
- C63: 17 DESCANSO.
- H87: DESCUENTO 15 MIN.
- C88: 24 DESCANSO.
- H92: DESCUENTO 45 MIN.
- H100: DESCUENTO 40 MIN.
- D103: DESCUENTO 6 HRS Y 5 MIN.
- D104: 6 HRS.
- D105: 5 MIN.

### 15. MERLY MORENO

**Función:** control individual. Tiene 96 marcas entre 2026-07-31 y 2026-08-26, y 168 fórmulas.

**Qué enseña para SISMOC:** El encabezado indica lunes, pero varias notas semanales corresponden a otros días. Validar calendario con la responsable.

**Evidencia y anotaciones:**

- C1: DESCANSO LUNES.
- C3: 30 DESCANSO.
- C28: 06 DESCANSO.
- C53: 13 DESCANSO.
- C78: 20 DESCANSO.
- C103: 27 DESCANSO.

### 16. FELIX ALLENDE

**Función:** control individual. Tiene 92 marcas entre 2026-07-31 y 2026-08-26, y 148 fórmulas.

**Qué enseña para SISMOC:** Descanso y feriado coincidentes, compensación y descuento. CUADRO contiene FERNANDO ALLENDE: confirmar identidad mediante identificadores.

**Evidencia y anotaciones:**

- C1: DESCANSO JUEVES.
- C3: 30 DESCANSO.
- A24: DESCANSO Y FERIADO.
- C52: 13 DESCANSO.
- H61: COMPENSADO 16/08.
- H64: DESCUENTO 1 HR.
- C75: 20 DESCANSO.
- C98: 27 DESCANSO.

### 17. HEMELY YAMUNAQUE

**Función:** control individual. Tiene 51 marcas entre 2026-07-30 y 2026-08-28, y 84 fórmulas.

**Qué enseña para SISMOC:** Vacaciones del 1 al 16. El resumen la identifica como HEMELY y no con el nombre completo de la pestaña.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGOS.
- C13: 01 - 16 VACACIONES.
- C38: 23 DESCANSO.

### 18. ANGIE SANCHEZ

**Función:** control individual. Tiene 84 marcas entre 2026-07-30 y 2026-08-27, y 156 fórmulas.

**Qué enseña para SISMOC:** Reunión fuera del centro habitual y feriado. Registrar actividades autorizadas que justifican horarios especiales.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGO.
- C11: 02 DESCANSO.
- A16: REUNION CASA ANDINA.
- C24: 06 FERIADO.
- C31: 09 DESCANSO.
- C74: 23 DESCANSO.

### 19. CARLOS PLAZA

**Función:** control individual. Tiene 57 marcas entre 2026-07-30 y 2026-08-28, y 119 fórmulas.

**Qué enseña para SISMOC:** Vacaciones breves y citas médicas. Las incidencias pueden abarcar días completos o parte de una jornada.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGO.
- C11: 02 DESCANSO.
- C18: 05 - 07 VACACIONES.
- C21: 09 DESCANSO.
- C38: 16 DESCANSO.
- A51: CITA MEDICA.
- C55: 23 DESCANSO.
- A58: CITA MEDICA.

### 20. DIANA CHOQUEHUANCA

**Función:** control individual. Tiene 55 marcas entre 2026-07-30 y 2026-08-28, y 123 fórmulas.

**Qué enseña para SISMOC:** Cumpleaños, descanso completo y medio día. Se requieren permisos con duración parcial.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGO.
- C10: 02 DESCANSO.
- C19: 06 FERIADO.
- C24: 09 DESCANSO.
- C39: 16 DESCANSO.
- A52: CUMPLEAÑOS.
- C54: DESCANSO POR CUMPLEAÑOS.
- C55: 23 DESCANSO.
- A56: DESCANSO MEDIO DIA POR CUMPLEAÑOS.

### 21. DIEGO VELIZ

**Función:** control individual. Tiene 70 marcas entre 2026-07-30 y 2026-08-28, y 140 fórmulas.

**Qué enseña para SISMOC:** Jornadas con descanso dominical y feriado. Útil para revisar la plantilla de personal con horarios distintos de boletería.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGO.
- C12: 02 DESCANSO.
- C23: 06 FERIADO.
- C28: 09 DESCANSO.
- C45: 16 DESCANSO.
- C62: 23 DESCANSO.

### 22. TERRONES YANELI

**Función:** control individual. Tiene 65 marcas entre 2026-07-30 y 2026-08-28, y 136 fórmulas.

**Qué enseña para SISMOC:** Once errores #REF! en nocturnidad, bases variables y excesos negativos. J6 muestra 8 h nocturnas aunque sus marcas de ese bloque son diurnas: revisar referencias.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGO.
- C11: 02 DESCANSO.
- C20: 06 FERIADO.
- C27: 10 DESCANSO.
- C46: 16 DESCANSO.
- C65: 23 DESCANSO.

**Errores guardados:** J26, J33, J39, J45, J48, J58, J64, J67, J69, J71, J73 contienen #REF!.

### 23. PAUL HARRIS

**Función:** fuente de marcaciones de la sede. Contiene 576 registros fechados. entre 2026-07-27 y 2026-08-28. No tiene fórmulas.

**En el sistema:** importar como eventos originales con sede, equipo, identificador local, fecha y hora. Conservar fila de origen y resolver identidad antes de calcular jornadas.

### 24. SEGUNDO AGAPITO

**Función:** control individual. Tiene 104 marcas entre 2026-07-30 y 2026-08-27, y 175 fórmulas.

**Qué enseña para SISMOC:** Auxilios mecánicos fuera de sede y trabajo en descansos. La actividad operativa explica cambios de horario y debe quedar vinculada a la jornada.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGO.
- A4: AUXILIO MECANICO AL B6D EN SAN JUAN.
- A16: TRABAJÓ DESCANSO.
- C30: 06 FERIADO.
- A33: AUXILIO MECANICO B4E A SAN JUAN.
- A39: TRABAJÓ DESCANSO.
- A45: AUXILIO MECANICO AL B4E EN EL DISTRITO DE SAN JUAN.
- A65: AUXILIO MECANICO B4E EN EL PEAJE DE PACANGUILLA.
- A91: TRABAJÓ DESCANSO.

### 25. ROBERTO RIVERA

**Función:** control individual. Tiene 94 marcas entre 2026-07-30 y 2026-08-27, y 161 fórmulas.

**Qué enseña para SISMOC:** Auxilio mecánico, descanso trabajado y falta con descuento. No identificarlo solo por el apellido Rivera.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGO.
- C16: 02 DESCANSO.
- A29: FERIADO.
- C39: 09 DESCANSO.
- A42: AUXILIO MECANICO CARRETERA CAJAMARCA B6D.
- A62: TRABAJÓ DESCANSO.
- C76: 20 NO TRABAJÓ.
- H76: DESCUENTO 1 DÍA.
- C85: 23 DESCANSO.

### 26. MANUEL MOSQUEIRA

**Función:** control individual. Tiene 102 marcas entre 2026-07-30 y 2026-08-27, y 174 fórmulas.

**Qué enseña para SISMOC:** Descanso semanal y feriado. La misma persona puede marcar en distintas sedes; conservar origen por marcación.

**Evidencia y anotaciones:**

- C1: DESCNASO MARTES.
- C23: 04 DESCANSO.
- A30: FERIADO.
- C50: 11 DESCANSO.
- C75: 18 DESCANSO.
- C100: 25 DESCANSO.

### 27. PEDRO CHAVESTA

**Función:** control individual. Tiene 96 marcas entre 2026-07-30 y 2026-08-27, y 168 fórmulas.

**Qué enseña para SISMOC:** Descansos y feriado. Las fuentes contienen variantes del nombre: usar una equivalencia de identidad.

**Evidencia y anotaciones:**

- C1: DESCASNSO DOMINGOS.
- C15: 02 DESCANSO.
- C28: 06 FERIADO.
- C37: 09 DESCANSO.
- C62: 16 DESCANSO.
- C87: 23 DESCANSO.

### 28. JUAN ZAPATA

**Función:** control individual. Tiene 5 marcas entre 2026-07-30 y 2026-07-31, y 7 fórmulas.

**Qué enseña para SISMOC:** Solo cinco marcas, de julio, y una nota extensa de vacaciones. No generar faltas para todo agosto sin interpretar esa incidencia.

**Evidencia y anotaciones:**

- C1: DESCANSO VIERNES.
- C10: 31 - 28 VACACIONES.

### 29. TRUJILLO

**Función:** fuente de marcaciones de la sede. Contiene 66 registros fechados. entre 2026-07-31 y 2026-08-28. No tiene fórmulas.

**En el sistema:** importar como eventos originales con sede, equipo, identificador local, fecha y hora. Conservar fila de origen y resolver identidad antes de calcular jornadas.

### 30. JORGE AGUILAR

**Función:** control individual. Tiene 65 marcas entre 2026-07-31 y 2026-08-28, y 112 fórmulas.

**Qué enseña para SISMOC:** Trabaja con varios días de descanso semanales y vacaciones. No sirve un calendario universal de seis días.

**Evidencia y anotaciones:**

- C1: DESCANSA MARTES MIERCOLES Y JUEVES.
- C4: 24 - 30 VACACIONES.
- C21: 4, 5 Y 6 DESCANSO.
- C38: 11, 12 Y 13 DESCANSO.
- C55: 18, 19 Y 20 DESCANSO.
- C72: 25. 26 Y 27 DESCANSO.

### 31. GACELA

**Función:** fuente de marcaciones de la sede. Contiene 108 registros fechados. entre 2026-07-27 y 2026-08-28. No tiene fórmulas.

**En el sistema:** importar como eventos originales con sede, equipo, identificador local, fecha y hora. Conservar fila de origen y resolver identidad antes de calcular jornadas.

### 32. NANCY FLORES

**Función:** control individual. Tiene 88 marcas entre 2026-07-30 y 2026-08-27, y 154 fórmulas.

**Qué enseña para SISMOC:** Día no trabajado, descuento y vacaciones breves. La hoja fuente GACELA contiene más de una persona.

**Evidencia y anotaciones:**

- C1: DESCANSO DOMINGO.
- C15: 02 DESCANSO.
- A28: FERIADO.
- C32: 07 NO TRABAJÓ.
- H32: DESCUENTO 1 DÍA.
- C37: 09 DESCANSO.
- C62: 16 DESCANSO.
- C63: 17 Y 18 VACACIONES.
- C80: 23 DESCANSO.

### 33. CAJAMARCA

**Función:** fuente de marcaciones de la sede. Contiene 1.244 registros fechados. entre 2026-07-27 y 2026-08-28. No tiene fórmulas.

**En el sistema:** importar como eventos originales con sede, equipo, identificador local, fecha y hora. Conservar fila de origen y resolver identidad antes de calcular jornadas.

**Particularidad:** hay identificadores cortos y nombres que también son números. Incorporar un catálogo de equivalencias por dispositivo y revisar el significado de Estado; no deducirlo solo por la posición de una marca.

### 34. MIDORI

**Función:** control individual. Tiene 96 marcas entre 2026-07-30 y 2026-08-27, y 165 fórmulas.

**Qué enseña para SISMOC:** Permisos por salud, compensaciones y salida anticipada. Debe poder justificarse una parte de la jornada.

**Evidencia y anotaciones:**

- B2: LUNES DESCANSA.
- B21: DESCANSO 03/08 LUNES.
- A31: TRABAJÓ FERIADO.
- B47: DESCANSO 10/08 LUNES.
- B73: DESCANSO 17/08 LUNES.
- B83: PIDIO PERMISO POR SALUD.
- G84: DESCUENTO 1 DÍA.
- G96: COMPENSADO DEL 27/08.
- B97: DESCANSO 24/08 LUNES.
- G102: COMPENSADO DEL 27/08.
- A107: SALIÓ 2:12 PORQUE TENIA CITA EN EL SEGURO.
- G110: DESCUENTO 30 MIN.

### 35. CELESTE

**Función:** control individual. Tiene 92 marcas entre 2026-07-30 y 2026-08-27, y 161 fórmulas.

**Qué enseña para SISMOC:** Permisos y salidas anticipadas con evidencia. Sus incidencias necesitan documento de respaldo y aprobación.

**Evidencia y anotaciones:**

- B2: DOMINGO DESCANSA.
- B17: DESCANSO DOMINGO 02/08.
- A31: TRABAJÓ FERIADO.
- B43: DESCANSO DOMINGO 09/08.
- A53: PERMISO PORQUE SU HIJO SE ENRONCHO Y SALIO TEMPRANO.
- G54: DESCUENTO 5 HRS Y 30 MIN.
- B63: PIDIO PERMISO PORQUE TUVO QUE LLEVAR AL ALERGOLOGO A SU HIJO, ENVIO EVIDENCIA.
- G63: DESCUENTO 1 DÍA.
- B65: DESCANSO DOMINGO 16/08.
- A67: SALIO TEMPRANO PORQUE TENIA QUE IR A CITA.
- G70: DESCUENTO 30 MIN.
- A83: ENTRÓ TARDE PORQUE TUVO ANALISIS.
- G84: DESCUENTO 1 HRAS.
- B89: DESCANSO DOMINGO 23/08.
- C109: DESCUENTO 7 HRS.
- C110: 7 HRS.
- C111: 0 MIN.

### 36. RIVERA

**Función:** control individual. Tiene 118 marcas entre 2026-07-30 y 2026-08-28, y 164 fórmulas.

**Qué enseña para SISMOC:** Coberturas de compañeros y cambio de descanso. Hay jornadas con más de cuatro marcas; sumar segmentos de trabajo.

**Evidencia y anotaciones:**

- C2: LUNES DESCANSA.
- C21:  DESCANSO LUNES 03/08 .
- B28: TRABAJÓ FERIADO.
- C47:  DESCANSO LUNES 10/08 .
- B53: CUBRIO A MIDORI POR ESO ENTRO A ESA HORA.
- B67: CUBRIÓ A CELESTE.
- C81:  DESCANSO LUNES 17/08 .
- B91: CUBRIÓ A MIDORI.
- B113: CAMBIÓ DIA DE DESCANSO PARA EL VIERNES 28.

### 37. PASAPERA

**Función:** control individual. Tiene 100 marcas entre 2026-07-30 y 2026-08-27, y 174 fórmulas.

**Qué enseña para SISMOC:** Descuentos parciales y feriado trabajado. El total manual de descuentos debe reconciliar con su detalle.

**Evidencia y anotaciones:**

- C2: SÁBADO DESCANSA.
- C13: DESCANSO SÁBADO 01/08 .
- B31: TRABAJÓ FERIADO.
- C39: DESCANSO SÁBADO 08/08 .
- H48: DESCUENTO 20 MIN.
- H56: DESCUENTO 45 MIN.
- H64: DESCUENTO 15 MIN.
- C65: DESCANSO SÁBADO 15/08 .
- C91: DESCANSO SÁBADO 22/08 .
- H100: DESCUENTO 40 MIN.
- D115: DESCUENTO 2 HRS.
- D116: 2 HRS.
- D117: 0 MIN.

### 38. MENDO

**Función:** control individual. Tiene 94 marcas entre 2026-07-30 y 2026-08-27, y 155 fórmulas.

**Qué enseña para SISMOC:** Observaciones sobre evidencia faltante, además de descuentos. No inventar una marcación por ausencia de foto.

**Evidencia y anotaciones:**

- C2: VIERNES DESCANSA.
- C9: DESCANSO 31/07 VIERNES.
- C35: DESCANSO 07/08 VIERNES.
- H52: DESCUENTO 20 MIN.
- B53: NO HAY FOTO EN WSP.
- B55: NO HAY FOTO EN WSP.
- C57: DESCANSO 14/08 VIERNES.
- H74: DESCUENTO 20 MIN.
- H78: DESCUENTO 20 MIN.
- B79: NO HAY FOTO EN WSP.
- C81: DESCANSO 21/08 VIERNES.
- H86: DESCUENTO 20 MIN.
- H94: DESCUENTO 15 MIN.
- H98: DESCUENTO 15 MIN.
- H102: DESCUENTO 15 MIN.
- H106: DESCUENTO 10 MIN.
- D109: DESCUENTO 2 HRS Y 15 MIN.
- D110: 2 HRS.
- D111: 15 MIN.

### 39. QUILICHE

**Función:** control individual. Tiene 100 marcas entre 2026-07-30 y 2026-08-27, y 175 fórmulas.

**Qué enseña para SISMOC:** Descanso de miércoles y feriado trabajado. Ejemplo de calendario repetitivo con excepciones.

**Evidencia y anotaciones:**

- C2: MIERCOLES DESCANSA.
- C29: DESCANSO 05/08 MIERCOLES.
- B31: TRABAJÓ FERIADO.
- C55: DESCANSO 12/08 MIERCOLES.
- C81: DESCANSO 19/08 MIERCOLES.
- C107: DESCANSO 26/08 MIERCOLES.

### 40. ABISAG

**Función:** control individual. Tiene 100 marcas entre 2026-07-30 y 2026-08-27, y 173 fórmulas.

**Qué enseña para SISMOC:** Compensación entre fechas y descuento parcial. En el resumen figura ABY ABISSAG: confirmar equivalencia.

**Evidencia y anotaciones:**

- C2: MARTES DESCANSA.
- H20: COMPENSADO 03/08.
- H25: DESCUENTO 15 MIN.
- C26: DESCANSO 04/08 MARTES.
- B32: TRABAJÓ FERIADO.
- C52: DESCANSO 11/08 MARTES.
- C78: DESCANSO 18/08 MARTES.
- C104: DESCANSO 25/08 MARTES.

### 41. LUZ MARINA

**Función:** control individual. Tiene 100 marcas entre 2026-07-30 y 2026-08-27, y 175 fórmulas.

**Qué enseña para SISMOC:** Descanso de miércoles y feriado trabajado. Separar calendario previsto y asistencia real.

**Evidencia y anotaciones:**

- C2: MIERCOLES DESCANSA.
- C29: DESCANSO MIERCOLES 05/08 .
- B31: TRABAJÓ FERIADO.
- C55: DESCANSO MIERCOLES 12/08 .
- C81: DESCANSO MIERCOLES 19/08 .
- C107: DESCANSO MIERCOLES 26/08 .

### 42. EMERITO

**Función:** control individual. Tiene 108 marcas entre 2026-07-30 y 2026-08-27, y 175 fórmulas.

**Qué enseña para SISMOC:** Cubre a Rivera en varios días. Registrar a quién cubre y qué horario se aplicó en cada fecha.

**Evidencia y anotaciones:**

- C2: SÁBADO DESCANSA.
- C13: DESCANSO 01/08 SABADO.
- B22: CUBRIO A RIVERA.
- B33: TRABAJÓ FERIADO.
- C41: DESCANSO 08/08 SABADO.
- B51: CUBRIO A RIVERA.
- C71: DESCANSO 15/08 SABADO.
- B81: CUBRIO A RIVERA.
- C99: DESCANSO 22/08 SABADO.

### 43. ANGULO

**Función:** control individual. Tiene 4 marcas entre 2026-07-31 y 2026-07-31, y 7 fórmulas.

**Qué enseña para SISMOC:** Solo cuatro marcas del 31 de julio. La hoja no demuestra por sí sola asistencia o falta durante agosto.

**Evidencia y anotaciones:**

- D2: MARTES DESCANSA.

### 44. ROJAS ALAN

**Función:** control individual. Tiene 102 marcas entre 2026-08-01 y 2026-08-27, y 163 fórmulas.

**Qué enseña para SISMOC:** Cubre a Silvio antes de su jornada habitual. Nocturnidad y horas de descanso incluyen valores manuales.

**Evidencia y anotaciones:**

- D2: JUEVES DESCANSA.
- B21: CUBRIÓ A SILVIO.
- C27: DESCANSO JUEVES 06/08.
- B49: CUBRIÓ A SILVIO.
- C55: DESCANSO JUEVES 13/08.
- B77: CUBRIÓ A SILVIO.
- C83: DESCANSO JUEVES 20/08.
- B105: CUBRIÓ A SILVIO.
- B111: CUBRIÓ A SILVIO.
- C113: DESCANSO JUEVES 27/08.

### 45. SILVIO

**Función:** control individual. Tiene 46 marcas entre 2026-07-31 y 2026-08-25, y 46 fórmulas.

**Qué enseña para SISMOC:** Jornadas de unas tres horas y vacaciones desde el 27. G representa duración trabajada en varios bloques, no exceso sobre ocho horas.

**Evidencia y anotaciones:**

- C2: MIERCOLES DESCANSA.
- C17: MIERCOLES 05/08 DESCANSO.
- B19: TRABAJÓ FERIADO.
- C31: MIERCOLES 12/08 DESCANSO.
- C45: MIERCOLES 19/08 DESCANSO.
- C59: MIERCOLES 26/08 DESCANSO.
- C61: JUEVES 27/08 SALIO DE VACACIONES.

### 46. TERÁN

**Función:** control individual. Tiene 96 marcas entre 2026-07-31 y 2026-08-27, y 168 fórmulas.

**Qué enseña para SISMOC:** Descanso de martes, feriado trabajado y combinación de turnos diurnos y de tarde. Revisar la clasificación de cada tramo.

**Evidencia y anotaciones:**

- C2: MARTES DESCANSA.
- C5: DESCANSO JUEVES 30/07.
- C23: DESCANSO MARTES 04/08.
- B29: TRABAJÓ FERIADO.
- C49: DESCANSO MARTES 11/08.
- C75: DESCANSO MARTES 18/08.
- C101: DESCANSO MARTES 25/08.

### 47. JAEN

**Función:** fuente de marcaciones de la sede. Contiene 283 registros fechados. entre 2026-07-27 y 2026-08-28. No tiene fórmulas.

**En el sistema:** importar como eventos originales con sede, equipo, identificador local, fecha y hora. Conservar fila de origen y resolver identidad antes de calcular jornadas.

### 48. GRECIA

**Función:** control individual. Tiene 100 marcas entre 2026-07-30 y 2026-08-27, y 175 fórmulas.

**Qué enseña para SISMOC:** Marcación incompleta contrastada con ventas y cambios de descanso. La corrección requiere evidencia y trazabilidad.

**Evidencia y anotaciones:**

- B3: DESCANSO MIERCOLES.
- B29: DESCANSO MIERCOLES 05/08.
- A31: TRABAJÓ FERIADO.
- A51: SOLO MARCÓ SALIDA, PERO SE VERIFICÓ EN EL SISTEMA Y SI TIENE VENTAS.
- B55: DESCANSO MIERCOLES 12/08.
- B81: DESCANSO MIERCOLES 19/08.
- B95: CAMBIO DIA DE DESCANSO, TRABAJO EL MIERCOLES 26.
- A105: TRABAJÓ DIA NORMAL PORQUE YA DESCANSÓ DOMINGO.

### 49. JUANITA

**Función:** control individual. Tiene 48 marcas entre 2026-07-30 y 2026-08-27, y 60 fórmulas.

**Qué enseña para SISMOC:** Calendario de martes, miércoles y jueves, con cambios entre compañeras. En varios bloques falta la base y G conserva el tiempo trabajado.

**Evidencia y anotaciones:**

- C3: TRABAJA: MARTES, MIERCOLES Y JUEVES.
- B17: TRABAJÓ FERIADO.
- B29: CAMBIÓ DIA DE DESCANSO  CON TATIANA.
- B41: CAMBIO DIA POR GRECIA, MIERCOLES 26 DESCANSA.

### 50. EVELYN

**Función:** control individual. Tiene 28 marcas entre 2026-08-20 y 2026-08-26, y 49 fórmulas.

**Qué enseña para SISMOC:** Solo hay marcas del 20 al 26 de agosto. No deducir una fecha de ingreso contractual únicamente de esa cobertura.

**Evidencia y anotaciones:**

- C3: DESCANSO JUEVES.
- C33: DESCANSO JUEVES 27/08.

### 51. CUADRO

**Función:** resumen de horas por trabajador y fecha. Su explicación detallada está en la siguiente sección. **En el sistema:** generar este informe desde jornadas aprobadas y ajustes, sin volver a digitar los tiempos.

## CUADRO explicado

El encabezado C1:AH1 contiene los días 30, 31, 01 y luego 02 a 30; AI es TOTAL. El encabezado no contiene fechas completas. Mezcla días de dos meses y no llega al 31 de agosto. Las marcaciones fuente llegan hasta el 28/08; no hay base para afirmar que el mes está completo ni para deducir el corte oficial de planilla.

Hay 38 bloques de trabajadores. Cada bloque suele tener una fila de nombre y cuatro conceptos:

| Concepto | Lectura del contenido | Equivalente propuesto |
|---|---|---|
| 2H | Horas del primer tramo de exceso, asociado a 25 % en controles individuales | Horas extras del primer tramo aprobadas |
| 3H | Exceso posterior a las dos primeras horas, no necesariamente tres horas completas | Horas extras del segundo tramo aprobadas |
| DESCANSO | Horas anotadas bajo esa categoría | Concepto separado; confirmar cuándo corresponde a descanso o feriado trabajado |
| SOBRE TASA NOCTURNA | Cantidades horarias, sin cálculo monetario visible | Horas nocturnas aprobadas |

Ejemplo de EMIR MONTEZA: AI4=50 h, AI5=15,1666667 h (15 h 10 min), AI6=8 h y AI7=63,4166667 h (63 h 25 min). Son los resultados guardados del resumen, no una conciliación con todas sus marcas.

No sumar las cuatro categorías como si fueran horas distintas: una hora nocturna puede coincidir con una hora extra. Tampoco el cero en la fila del nombre demuestra ausencia de trabajo: los valores están en las filas de conceptos.

### Observaciones concretas

- N96 contiene `=10/690`, mientras las conversiones de minutos a horas usan normalmente `/60`. Es una anomalía a confirmar, no una corrección aplicada.
- AI228 usa `SUM(E228:AH228)` y deja fuera C228 y D228, que sí contienen valores. Puede responder a un corte distinto, pero necesita explicación. La mayoría de los bloques suma desde C.
- Hay variantes de nombres como FERNANDO ALLENDE frente a la pestaña FELIX ALLENDE, SEGUNDO LLONTOP frente a SEGUNDO AGAPITO y jony RIVERA frente a RIVERA. Son candidatos de equivalencia, no identidades confirmadas.
- Solo hay 38 bloques frente a 43 controles individuales. No todos los trabajadores tienen el mismo resumen ni necesariamente el mismo tratamiento de conceptos.

## Problemas a resolver antes de convertirlo en reglas

| Evidencia | Consecuencia | Acción propuesta |
|---|---|---|
| Once #REF! en TERRONES YANELI | Nocturnidad no fiable en esas celdas | Recalcular a partir de los intervalos confirmados |
| TERRONES YANELI!J6 guarda 8 h nocturnas con marcas diurnas en D5:D6 | No basta con buscar errores de Excel | Revisar qué intervalos toma cada fórmula |
| G6/H6 en esa misma hoja son negativos | El exceso negativo llega a la categoría 25 % | Separar déficit de jornada y horas extras |
| Bases de 8 h, 8 h 45 min, 9 h 30 min y otras | No existe una sola base operativa en el archivo | Parametrizar y aprobar horarios según trabajador y vigencia |
| Números y duraciones mezclados | Riesgo de multiplicar horas por 24 indebidamente | Conservar valor original y unidad interpretada |
| Descansos anotados que no siempre coinciden con el encabezado | El texto no define un calendario consistente | Programación semanal más excepciones fechadas |
| Vacaciones, permisos, coberturas y descuentos en texto | Parte esencial del proceso queda fuera de las marcas | Entidades de incidencias y ajustes con evidencia |
| Mismo trabajador en varias fuentes | Una hoja por sede no equivale a una persona | Identidad central y equivalencias por equipo |
| Fuentes y controles contienen la misma actividad | Importar todas las hojas como eventos duplica información | Fuentes para eventos; controles para conciliación e incidencias |
| CUADRO se completa por separado | Cambios de origen no se reflejan solos | Informe derivado con estado de revisión y cierre |

## Comparación con el código actual

Se revisaron `asistencia/models.py`, `core/models.py` y `asistencia/services/zkteco_parser.py`. No se ejecutó una importación ni se escribió en la base de datos.

La base ya dispone de Usuario, turno, sede del usuario, identificador ZKTeco, MarcacionBiometrica, ResumenAsistenciaDiaria y CargaArchivoAsistencia. También existen origen de marcación, coordenadas, fotografía y un indicador de verificación contable. Estos campos permiten avanzar sin rehacer todo el módulo.

Sin embargo, el comportamiento del importador no reproduce este libro:

1. `procesar()` envía todas las hojas a `_procesar_hoja_individual()` cuando hay más de una. Las sedes contienen muchas personas y deben tener otra ruta.
2. `_procesar_hoja_individual()` busca fechas entre todos los valores y usa el nombre de la pestaña como persona. No extrae de forma estructurada identificador, refrigerio, tipo de evento ni incidencias.
3. La ruta individual asigna ENTRADA a todas las marcas. Hace falta distinguir evento reportado, evento inferido y corrección manual.
4. La búsqueda por la primera palabra del nombre y la primera coincidencia es ambigua. Las variantes de nombres y apellidos requieren equivalencias verificadas.
5. La ruta tabular no reconoce literalmente `No.` ni `ID Numero` con su normalización actual, y tampoco mapea `Estado`. No debe asumirse compatible con estas fuentes por el solo hecho de ser tabular.
6. La consolidación agrupa por fecha calendario y toma primera y última marca. Pierde el emparejamiento de jornadas que atraviesan medianoche y la separación en varios tramos.
7. Descuenta una hora fija si el intervalo supera seis horas. El ejemplo de Emir muestra que el archivo usa refrigerios observados de otra duración.
8. Usa un turno administrativo general para la hora esperada, aunque Usuario tiene un turno asignable. Hace falta aplicar la programación vigente de cada persona.
9. La nocturnidad solo se calcula después de las 22:00 cuando la última hora alcanza esa hora. No cubre las madrugadas como la de Emir ni todos los cruces de fecha.
10. La auditoría usa el mes de ejecución, no el periodo del archivo. Una carga de agosto ejecutada en octubre quedaría con periodo de octubre.
11. Las marcas creadas no reciben el lote `carga_origen`; la auditoría se crea después. Hace falta enlazar lote, hoja y fila para poder rastrear cada resultado.
12. Permisos existen como estado diario, pero vacaciones, cambios de descanso, compensaciones y descuentos parciales necesitan datos propios. Un texto libre no alcanza para calcularlos de forma reproducible.

Las reglas sobre vueltas y descansos de conductores presentes en el código no quedan justificadas por este libro de asistencia. Revisar el archivo específico de choferes antes de definirlas.

## Diseño recomendado para continuar

| Componente | Información mínima | Finalidad |
|---|---|---|
| Identidad biométrica | Trabajador, sede/equipo, ID local, vigencia | Asociar cada evento sin depender del nombre |
| Lote de importación | Archivo, huella del archivo, periodo solicitado, usuario, estado | Evitar cargas repetidas y conservar procedencia |
| Marca original | Fecha y hora, ID local, sede, equipo, verificación, hoja/fila | Preservar evidencia sin sustituirla por un cálculo |
| Programación | Trabajador, fecha o patrón semanal, tramos previstos, descanso | Saber qué debía trabajar cada persona |
| Jornada y tramos | Inicio y fin completos, tipo de tramo, marcas utilizadas | Resolver refrigerios, medianoche y coberturas |
| Incidencia | Tipo, intervalo, motivo, evidencia, aprobación | Vacaciones, permisos, citas y marcaciones incompletas |
| Ajuste | Minutos u horas, concepto, jornada de origen/destino, aprobación | Compensaciones y descuentos sin reescribir marcas |
| Resultado diario | Trabajo, déficit, extras por tramo, nocturnidad, incidencias | Explicar cómo se obtuvo cada concepto |
| Cierre del periodo | Fecha inicial/final, revisión, responsable y versión | Generar CUADRO reproducible para contabilidad |

No deben aprobarse automáticamente los resultados porque coincidan con una celda del Excel. Primero se confirma la regla, se calcula desde la evidencia y luego se compara la diferencia con el control histórico.

## Orden de desarrollo y casos de aceptación

1. Clasificar hojas e importar las seis fuentes a una vista previa: debe mostrar 4.287 registros fechados antes de conciliar, sin crear usuarios llamados CHICLAYO o CAJAMARCA.
2. Resolver identificadores locales y personas. Una recarga del mismo archivo no debe duplicar eventos; conservar también la sede de cada marca.
3. Construir jornadas por fecha y hora completas. Probar ALEJANDRO ARTEAGA D3:D4: conservar una jornada de 11:39:34 atravesando medianoche.
4. Calcular trabajo por tramos. Probar EMIR MONTEZA D3:D6: 10:54:55 de trabajo efectivo y 00:45:02 de refrigerio según los tramos del archivo.
5. Incorporar programación e incidencias. Probar vacaciones de JHON DAVILA, calendario parcial de JUANITA y cobertura de ROJAS ALAN.
6. Calcular conceptos con reglas confirmadas. Probar exceso negativo en TERRONES YANELI y nocturnidad de madrugada en EMIR MONTEZA.
7. Conciliar con controles individuales y CUADRO, mostrando diferencia, motivo y ajuste aprobado. No importar ambos como eventos adicionales.
8. Generar el resumen contable con fechas completas y cierre del periodo.

## Decisiones que faltan de la operación

- Inicio y fin oficiales del periodo llamado agosto, y criterio para jornadas que cruzan el corte.
- Significado de las bases variables y del tratamiento de JUANITA y SILVIO.
- Criterio de redondeo de segundos a minutos: CUADRO contiene valores manuales y no basta para inferir una única regla.
- Qué significa cada valor de Estado y cómo se resuelven marcas faltantes o sobrantes.
- Equivalencias de nombres, DNI e identificadores cortos por dispositivo.
- Regla para feriados, descansos trabajados, permisos, descuentos y compensaciones, con quién los aprueba.

Estas decisiones pueden documentarse mientras se construyen la importación con vista previa y la trazabilidad, que no dependen de fijar todavía el cálculo contable final.
