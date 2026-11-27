# Dos productos independientes

| Producto | Repositorio | Uso |
| --- | --- | --- |
| SISMOC Demostración | `sbecerranilsonj-tech/SISMOC_CUMBE.` | Web completa, API y Flutter; presentación académica en Railway |
| SISMOC Escritorio | `nsilupu-30/SISMOC_CUMBE` | Gestión local de Yaneli: importación de archivos, asistencia, bancos, conductores y reportes |

Se preparan en `versiones/demostracion` y `versiones/escritorio`, cada una con su
propio `.git` y `origin`. A partir de la separación, editar y probar directamente
en la carpeta de la edición correspondiente. Una mejora no se copia a la otra de
forma automática. Para compartir una corrección, revisarla y aplicarla en ambos
repositorios de forma expresa.

Las bases, contraseñas, sesiones y archivos reales nunca se publican en GitHub.
La instalación actual y sus datos se conservan en su ubicación original. No hay
sincronización automática entre la empresa y Railway.

La demostración conserva Django/PostgreSQL y todas las funciones móviles. El
escritorio desactiva rutas y menús móviles y usa una base local separada para una
computadora. El acceso del gerente desde otra computadora requiere una futura
modalidad servidor/cliente y comunicación autorizada entre redes.

El instalador se compila con `desktop/Compilar.ps1` en la edición de escritorio.
La migración de los datos existentes y la prueba del instalador en Windows limpio
se deben completar antes de reemplazar la instalación que utiliza la empresa.

## Documentos de entrada

- Demostración: `README.md`, `docs/RAILWAY.md`, `mobile/README.md`.
- Escritorio: `README.md`, `desktop/README.md`, `desktop/instalador.iss`.
