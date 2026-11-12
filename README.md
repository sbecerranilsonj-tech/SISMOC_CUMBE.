# SISMOC CUMBE

Sistema web Django y aplicación Flutter para operación, asistencia, conciliación
bancaria, conductores y embarque de Transportes El Cumbe.

## Publicación de pruebas en Railway

Seguir **[docs/RAILWAY.md](docs/RAILWAY.md)**. El repositorio contiene el código y
las migraciones; no contiene los datos de la empresa ni credenciales.

- Python 3.12, Django, PostgreSQL.
- `Dockerfile` y `railway.json`: construcción y comprobación `/health/`.
- `deploy/start.py`: migraciones, administrador inicial opcional, estáticos y Gunicorn.
- `.env.railway.example`: nombres de variables sin secretos reales.
- Volumen `/data` para archivos privados; PostgreSQL con su propio volumen.
- `mobile/`: código de la app; el teléfono utiliza la URL HTTPS del servicio Django.

La primera publicación crea una base vacía. Las cuentas y archivos locales deben
importarse por un procedimiento privado, separado del repositorio.

## Desarrollo

Instalar `requirements.txt` en un entorno virtual, configurar las variables locales,
ejecutar `python manage.py migrate`, `python manage.py createsuperuser` y
`python manage.py runserver`. Para el cliente consultar `mobile/README.md`.

No publicar `.env`, claves, archivos bancarios, fotos, informes de trabajadores,
bases SQLite ni volcados SQL/JSON. Guardar copias de la base y archivos en un medio
privado. Este repositorio no concede una licencia de reutilización comercial.

## Edición académica independiente

Repositorio: [sbecerranilsonj-tech/SISMOC_CUMBE.](https://github.com/sbecerranilsonj-tech/SISMOC_CUMBE.).
Contiene toda la web, API, código Flutter en `mobile/lib` y pruebas de la app.
Usar datos de demostración; no se conecta a la base real de la empresa.
La edición de escritorio de Yaneli se mantiene por separado.
