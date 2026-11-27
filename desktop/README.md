# SISMOC Escritorio · Gestión de la empresa

Ventana Windows para Contabilidad: importar archivos, revisar asistencia, controlar
bancos y conductores y generar reportes. Conserva los diseños y módulos web de
gestión. No requiere Railway ni pagos de alojamiento para su uso local.

## Separación

- Repositorio: `nsilupu-30/SISMOC_CUMBE`.
- El cliente Flutter no se incluye en esta edición.
- Las rutas móviles, el panel de activaciones y los enlaces a la API se deshabilitan.
- Los modelos y migraciones móviles se conservan internamente para evitar romper
  el historial de migraciones; esto no habilita el acceso de celulares.
- No se conecta automáticamente a PostgreSQL de Docker ni a Railway.

## Ejecutar desde el código (desarrollo)

En Windows con Python 3.12 de 64 bits:

```powershell
py -3.12 -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r desktop\requirements.txt
.\.venv-desktop\Scripts\python.exe desktop\launcher.py
```

Requiere Microsoft Edge WebView2 Runtime. La primera apertura permite crear una
cuenta de Contabilidad sin contraseña predefinida. El servidor Waitress se abre en
un puerto local libre y la ventana lo muestra sin barra de direcciones. Permite
descargar los reportes. Cerrar la ventana detiene este servidor: no es aún un
servicio de Windows para atender otros equipos.

## Datos y actualizaciones

Se almacenan por usuario Windows en `%LOCALAPPDATA%\SISMOC-CUMBE\Escritorio`:

| Carpeta o archivo | Contenido |
| --- | --- |
| `sismoc.sqlite3` | Base local de esta instalación |
| `.secret_key` | Clave privada local; no compartir ni subir a GitHub |
| `media`, `private_bancos`, `private_conductores` | Documentos y archivos importados |
| `backups` | Copias automáticas de la base antes de aplicar migraciones pendientes |
| `logs` | Diagnóstico de arranque |

La base y los documentos se guardan fuera del directorio de instalación. Una
actualización del programa no reemplaza los datos. Para una copia completa,
cerrar SISMOC y copiar la carpeta **Escritorio** a un medio privado externo.
Los respaldos automáticos SQLite no incluyen los documentos: no sustituyen esa
copia completa. No copiar bases ni `.env` dentro de este repositorio.

El primer arranque usa una base nueva. La información existente de PostgreSQL
debe migrarse y validarse por separado antes de entregar el programa a Yaneli.

## Generar el instalador

Instalar Inno Setup 6 y ejecutar `desktop/Compilar.ps1`. Genera primero la carpeta
`desktop/dist/SISMOC` con el ejecutable y sus dependencias. Con `ISCC.exe` en PATH,
genera `desktop/instaladores/SISMOC-Escritorio-Instalador.exe`.
También se puede abrir `desktop/instalador.iss` con Inno Setup y compilarlo.

La receta de empaquetado debe probarse en un Windows limpio antes de entregar el
instalador. No se debe confundir este código con un instalador ya compilado y
certificado. Un ejecutable sin firma puede mostrar SmartScreen.

## El gerente y otras computadoras

Este primer arranque está limitado a `127.0.0.1` para la computadora principal.
No publicar SQLite en una carpeta compartida. Para varias computadoras hace falta
una modalidad servidor/cliente con base central, conexión entre las redes y permisos
por cuenta. Es un despliegue distinto que se debe preparar y probar antes de usarlo.
