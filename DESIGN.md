# Diseño visual de SISMOC-CUMBE

## Referencia elegida por el usuario

El 19/10/2026 el usuario pidió seguir el diseño de su proyecto anterior `TRABAJOS _ANTERIORES/DAD_B_Grupo3`. Se consultaron `app/(admin)/layout.tsx`, `app/globals.css`, `app/layout.tsx` y el logotipo `public/logocumbe.png`. Esta referencia reemplaza las propuestas visuales anteriores.

## Dirección y reglas

- Modo operativo: conservar periodos, filtros, permisos, validación y aprobación contable.
- Menú verde oscuro #101814, ancho 260 px, iconos SVG dentro de recuadros de 30 px. Opción activa naranja sobre fondo tenue. En escritorio puede contraerse; en móvil abre con botón y cierra con Escape.
- Área de trabajo #f8f9fc, paneles blancos con radios de 18–22 px y sombra inferior tenue. Cabecera blanca fija de 64 px con ubicación actual y menú de cuenta real.
- Geist local, como en el proyecto anterior, con licencia OFL en static/fonts. Títulos 21–28 px, texto principal 13–15 px, cifras tabulares.
- Naranja decorativo de la referencia #f07639. Botones con #bd4d14 para mantener contraste del texto blanco. Navegación activa #ff9a68 sobre fondo oscuro.
- Paneles de indicadores con iconos naranja, verde, azul y morado; todos muestran exclusivamente indicadores existentes en SISMOC. No copiar ventas, pasajes ni gráficos de datos que este proyecto no tiene.
- Mantener carga directa de archivos desde el botón inferior derecho, filtros desplegables y densidad de tablas. Sin recuadro intermedio de importación.
- Respetar foco visible, Escape, nombres accesibles y preferencias de movimiento reducido.

## Implementación

Tailwind CSS 4.3.0: editar assets/app.css y ejecutar npm run build:css. static/app.css se entrega compilado. interfaz.css conserva compatibilidad con los módulos existentes; Bootstrap permanece para las cuadrículas anteriores. El logotipo de referencia se copió a static/img/el-cumbe-marca.png. El proyecto anterior no se modificó.

## Revisión

| Antes | Después | Motivo |
|---|---|---|
| Menú azul con naranja sólido | Menú verde oscuro y selección naranja tenue con iconos en recuadros | Seguir la referencia elegida |
| Source Sans y Manrope | Geist local | Igualar la tipografía del trabajo anterior |
| Encabezado con título general | Ubicación de la sección y menú de cuenta | Seguir la estructura del panel anterior |
| Indicadores unidos | Paneles separados con iconos de color | Reproducir su composición con datos de SISMOC |

Renderizados Inicio, Asistencia y detalle con datos ficticios de una base de pruebas separada. Comprobados el menú de cuenta (incluido Escape), navegación entre secciones, fuente Geist y móvil de 390 px sin desbordamiento horizontal de página. Las tablas conservan desplazamiento interno.

## Archivo de propuesta anterior en Figma

https://www.figma.com/design/ShUszGw590CEz3Jy1KGNYp?node-id=1-2

La propuesta anterior es editable, pero no constituye la referencia visual vigente después de la elección de DAD_B_Grupo3.

Validación final: 93 pruebas de asistencia aprobadas tras conservar el nombre accesible del dashboard.

## Acceso adaptado al login anterior

El login usa el banner y logotipo horizontal de DAD_B_Grupo3, fotografía oscurecida a la izquierda y formulario blanco sobre fondo claro a la derecha. Mantiene usuario/DNI, contraseña, CSRF, destino next y evaluación por rol existentes. En móvil se oculta el banner y se prioriza el formulario. Comprobados mostrar/ocultar contraseña, formulario POST con CSRF y ancho de 390 px sin desbordamiento. La fuente Geist se sirve como TTF variable oficial para respetar los distintos pesos tipográficos.

## Resumen de revisión por trabajador · 20/10/2026

Cabecera compacta con inicial, nombre y datos agrupados; periodo y marcaciones en una fila; cuatro contadores de estado con etiquetas breves. Instrucciones en Cómo revisar. Cuando no hay jornadas listas se oculta el formulario de aprobación y se explica el estado; si todas las fechas están aprobadas se muestra Periodo aprobado. Mantener la confirmación obligatoria cuando sí existen jornadas listas. Verificado en escritorio y 390 px; 98 pruebas aprobadas.

Los estilos del resumen por trabajador se sirven desde static/revision_trabajador.css, enlazados por la propia plantilla para evitar depender de una versión anterior de app.css en el navegador. Verificada la hoja cargada y la distribución flex/grid en la ventana renderizada.

El detalle diario sigue el resumen compacto: identidad agrupada, fecha y estados separados, título Control diario y guía desplegable. Los criterios extensos se mantienen disponibles en un desplegable. Estilos propios en static/detalle_jornada.css, enlazados desde la plantilla. Verificados la carga de CSS, la ayuda y 390 px sin desbordamiento de página; se conserva el desplazamiento horizontal interno de la tabla.

Marcación manual: recuadro compacto con botón que abre un diálogo nativo independiente; conserva el formulario y copia de clasificaciones existentes al guardar. Fecha y hora en dos columnas en escritorio, una en móvil. Cancelar/Escape cierran únicamente el diálogo manual y devuelven el foco al botón. Descuentos/compensaciones en fila y criterios/observaciones agrupados en desplegables. Verificados apertura, cierre, foco y permanencia del detalle principal.

El formulario manual visible se limita a fecha, hora, tipo y motivo. Código/equipo se resuelve automáticamente con las identidades del trabajador y las marcas del día; no se solicita enlace de evidencia. Se preserva compatibilidad de validación interna y evidencia histórica. 100 pruebas de asistencia aprobadas.

Procedencia y tiempos: filas de hora/origen con metadatos desplegables por registro. Resumen visual de trabajo, refrigerio, tardanza y tiempo pendiente; intervalos, horario y ayuda en desplegables; comparación de horas guardadas y con ajustes permanece visible. Se conservan evidencia y auditoría originales. Verificados detalles de origen, intervalos y 390 px sin desbordamiento. 100 pruebas aprobadas.

## Paneles de procedencia y tiempos · 22/10/2026
Marcaciones con hora, evento y origen agrupados, sin repetir el primer y último registro. Horario con edición desplegable; cuatro cifras en una fila en escritorio y dos columnas en móvil. Tabla de conceptos sin desplazamiento interno; observaciones y explicación bajo desplegables. Estilos locales versionados para evitar caché anterior. Verificados ambos paneles en 1440 y 390 px, incluida la edición de horario y el detalle de procedencia, con datos ficticios.

