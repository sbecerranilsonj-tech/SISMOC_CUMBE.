# Publicar SISMOC en Railway (entorno de pruebas)

La web y la API móvil corren en un servicio Django. PostgreSQL es otro servicio del
mismo proyecto. Un volumen del servicio Django conserva los archivos importados.
No se necesita publicar la app en Play Store para estas pruebas.

## 1. Crear el proyecto y la base de datos

1. En Railway: **New Project > Empty Project**.
2. En el proyecto: **New > Database > PostgreSQL**. Mantener el nombre `Postgres`.
3. Añadir el servicio web: **New > GitHub Repo** y elegir este repositorio,
   rama `main`, directorio raíz `/`. Railway detecta `Dockerfile` y `railway.json`.
4. Puede fallar el primer despliegue mientras faltan variables: configurarlas
   antes de volver a desplegar.

## 2. Archivos persistentes

En el servicio web agregar un **Volume** montado en `/data`.
No montar el volumen de PostgreSQL en el servicio web: cada uno tiene el suyo.
El servicio web usará `/data/media`, `/data/private_bancos` y
`/data/private_conductores`. El disco del contenedor sin volumen es temporal.
Mantener **una réplica** para este entorno de pruebas.

## 3. Variables del servicio web

| Variable | Valor |
| --- | --- |
| `DEBUG` | `False` |
| `SECRET_KEY` | Un secreto aleatorio de al menos 50 caracteres, estable entre despliegues |
| `DATABASE_URL` | Referencia a `Postgres.DATABASE_URL`: `${{Postgres.DATABASE_URL}}` |
| `DATA_DIR` | `/data` |
| `BOOTSTRAP_ADMIN_USERNAME` | El usuario administrativo que elijas |
| `BOOTSTRAP_ADMIN_PASSWORD` | Contraseña nueva y única de al menos 12 caracteres |
| `BOOTSTRAP_ADMIN_EMAIL` | Tu correo administrativo |

Generar `SECRET_KEY` en una terminal de confianza con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Guardar el resultado únicamente en Railway. No subirlo a GitHub ni compartirlo en
capturas. Las credenciales locales de Docker y las cuentas locales no se copian.
No ejecutar `seed_sismoc` en la nube.

En **Settings > Networking > Generate Domain**, generar el dominio público.
Usar el puerto que Railway asigne en `PORT`; el arranque lo lee automáticamente.
Si el panel pide indicar un puerto destino explícito, definir `PORT=8000` en Variables
y seleccionar el mismo puerto `8000` en Networking.

`RAILWAY_PUBLIC_DOMAIN` se incorpora automáticamente a los hosts y orígenes CSRF.
Si no está disponible, o al usar un dominio propio, añadir:

```text
ALLOWED_HOSTS=tu-dominio.up.railway.app
CSRF_TRUSTED_ORIGINS=https://tu-dominio.up.railway.app
```

No usar `*` ni `DEBUG=True` para solucionar errores del despliegue.

## 4. Desplegar

Aplicar los cambios pendientes de Railway y desplegar. El contenedor ejecuta:

1. Comprobaciones de Django.
2. Migraciones pendientes sobre la base nueva.
3. Creación del administrador inicial **solo si no existe**.
4. `collectstatic` y Gunicorn con WhiteNoise para CSS, JS, fuentes y logos.

La comprobación de salud es `/health/`. Si falla, revisar **Deploy Logs**, sin
compartir variables secretas. Verificar `/login/`, estilos y acceso al panel.

Después de entrar, retirar `BOOTSTRAP_ADMIN_PASSWORD` y las demás variables
`BOOTSTRAP_ADMIN_*` y volver a desplegar. Reiniciar nunca cambia la contraseña de
una cuenta ya creada.

## 5. App móvil

En **Servidor de pruebas** de la app introducir `https://tu-dominio.up.railway.app`,
sin `/movil/` ni `/api/` al final. La app añade las rutas automáticamente.
No usar `localhost`, `127.0.0.1`, la IP Wi-Fi de la laptop ni `adb reverse`.
Activar la cuenta con un código generado por la **web de la nube**.
Las cuentas, sesiones y códigos locales no están en la nueva base de pruebas.

## 6. Datos y continuidad

El despliegue inicia una base nueva. No sube trabajadores, cuentas, marcaciones,
Excel, PDF, fotos ni copias de seguridad existentes. Importar datos de prueba desde
las pantallas o planificar una migración privada de la base y sus archivos; nunca
subir `dump_data.json`, `.env`, SQL o archivos de trabajadores al repositorio.
El lector ZKTeco en una red local no se vuelve accesible desde la nube:
para estas pruebas se puede continuar importando sus archivos Excel.

Comprobar desde datos móviles con el servidor de la laptop apagado. Verificar
activación, marcación, permisos, importación, pagos y persistencia tras reiniciar.
Los cambios posteriores se publican al subir nuevos commits a `main`.

La prueba y su crédito son limitados. Revisar Usage y realizar copias privadas de
PostgreSQL y del volumen antes de que termine. Datos de producción requieren un
entorno y copias de seguridad de la empresa.
