# Módulo bancario BCP

Dos apartados en el menú lateral: `/bancos/` (importación y validación en una
misma pantalla) y `/bancos/control/` (movimientos confirmados). Acceso para
contabilidad, gerencia y administración con cuenta activa. No genera Excel.

## Flujo de trabajo

- Consultar los estados por mes, archivo/cuenta y estado de validación.
- El botón inferior derecho «Subir estado de cuenta» abre el selector del PDF y
  envía el archivo al seleccionarlo, sin un formulario emergente.
- Revisar en la misma pantalla la cuenta, los saldos, las incidencias y los
  movimientos. Buscar por descripción conserva el saldo calculado en el orden
  completo del banco.
- Corregir los datos necesarios, comprobar saldos y validar para pasar a Control
  bancario. Se mantienen los permisos, bloqueos y auditoría existentes.
- La dirección anterior `/bancos/validacion/` redirige al apartado unificado con
  los archivos pendientes de validar.

## Activación

Se requiere reconstruir el servicio para instalar `pdfplumber` y aplicar la migración:

```powershell
docker compose up -d --build web
docker compose exec web python manage.py showmigrations bancos
docker compose exec web python manage.py test bancos
```

El comando de arranque existente ejecuta `migrate` antes de iniciar Django. Sin Docker,
instalar `requirements.txt` en el entorno del proyecto y ejecutar `python manage.py migrate`.

## Alcance

- PDF BCP en soles con texto seleccionable, hasta 20 MB y 500 páginas.
- Extrae cuenta, período, fechas, descripción, cargos y abonos por coordenadas.
- Conserva movimientos repetidos legítimos y el orden de origen para el saldo.
- Comprueba los totales de cargos y abonos del PDF y la ecuación de saldos.
- Un archivo idéntico abre su importación existente; se rechazan períodos superpuestos
  para la misma cuenta durante la importación.
- Las correcciones requieren motivo, se auditan y conservan el original.
- Solo un estado sin incidencias y con saldo comprobado puede pasar a control.
- Un estado validado queda bloqueado para edición; confirmar de nuevo no crea copias.
- Los PDF se guardan en `private_bancos/`, fuera de `MEDIA_ROOT`, y se entregan mediante
  una vista con permisos. Incluir este directorio en las copias de seguridad junto a la BD.
- Las líneas ilegibles bloquean la confirmación y requieren corregir el extractor; no se
  descartan ni se inventan movimientos para cuadrar saldos.

No incluye OCR, cruce con libro de caja, clasificación contable automática ni datos que
no estén en el PDF (hora, usuario, número de operación, sucursal). Validado no significa
conciliado contra los registros internos.

## Comprobación realizada en esta implementación

Pruebas aisladas con SQLite y rutas del módulo: flujo pendiente → validado, idempotencia,
permisos incluidos los PDF, diferencias e incidencias bloqueantes, auditoría de correcciones,
bloqueo de edición y renderizado de plantillas. Pruebas del extractor con coordenadas
sintéticas: signo según columna, repetidos, saldo separado y totales inconsistentes.

La migración coincide con los modelos. Queda pendiente ejecutar las pruebas con la
configuración completa de producción y el PDF real: el entorno de desarrollo denegó
el acceso a Docker y la conexión de pip al repositorio de paquetes.
