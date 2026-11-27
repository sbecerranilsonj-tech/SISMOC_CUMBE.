# SISMOC-CUMBE
### Sistema Integrado de Gestión Operativa, Asistencia y Conciliación
**Empresa de Transportes El Cumbe S.A.C.** (RUC: `20480397731`)  
Prácticas Pre Profesionales (1IS101) — Universidad Señor de Sipán (2026-II)

---

## 🚀 Tecnologías
- **Backend:** Python 3.12, Django 5.1/6.1, Django Ninja (FastAPI-like REST API), Pandas (Procesamiento de archivos ZKTeco y Excel).
- **Base de Datos:** SQLite (Desarrollo) / PostgreSQL 15 (Docker / Producción).
- **Seguridad:** JWT Bearer Token, Control de Acceso Basado en Roles (RBAC - 7 Roles).
- **Contenerización:** Docker & Docker Compose.

---

## 👥 Matriz de 7 Roles RBAC
1. 👑 **Gerente General** (`GERENTE_GENERAL`)
2. ⚙️ **Administrador del Sistema** (`ADMINISTRADOR`)
3. 📊 **Contadora General** (`CONTADORA`)
4. 🚌 **Conductor / Chofer** (`CONDUCTOR`)
5. 📱 **Operador en Bus / Embarcador** (`OPERADOR_EMBARQUE`)
6. 🎟️ **Vendedor / Boletería** (`BOLETERIA`)
7. 👔 **Empleado / Personal Administrativo** (`ADMINISTRATIVO`)

---

## ⚙️ Despliegue con Docker
```bash
docker-compose up --build
```

## 💻 Ejecución Local
```bash
# Crear entorno e instalar dependencias
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Migrar y poblar datos iniciales
python manage.py migrate
python manage.py seed_sismoc

# Iniciar servidor
python manage.py runserver 8000
```

- **Dashboard:** http://localhost:8000/
- **Swagger Docs:** http://localhost:8000/api/docs
- **Django Admin:** http://localhost:8000/admin/

## Interfaz con Tailwind CSS

Tailwind CSS 4.3.0 está integrado en las plantillas Django. El navegador recibe `static/app.css` compilado, sin un compilador externo en tiempo de ejecución.

Para trabajar los estilos:

```powershell
npm ci
npm run watch:css
```

Antes de entregar cambios:

```powershell
npm run build:css
```

Editar `assets/app.css`; conservar `static/app.css` y `package-lock.json` en el repositorio. El CSS compilado permite ejecutar Django y Docker sin instalar Node en el servidor. Se omite Preflight para conservar los formularios y las cuadrículas Bootstrap de los módulos existentes: es una integración progresiva, no una eliminación completa de Bootstrap.

Controles de interfaz: contraer navegación en escritorio, mostrar/ocultar filtros de asistencia y cambiar densidad de tablas. Menú y densidad se recuerdan solo en el navegador mediante preferencias locales; no alteran resultados contables.
# Programación de horarios por fecha

En **Asistencia → Programar horarios**, Contabilidad, Administración y Gerencia pueden registrar horarios confirmados y asignarlos a un trabajador por rango de fechas y días de la semana. Para una rotación, guardar cada semana con su turno correspondiente.

La programación se conserva aunque todavía no existan marcaciones. Al enviar las marcas a Asistencia se aplica el horario de la fecha. Cambiar un turno recalcula la tardanza de una secuencia completa y deja pendiente de revisión cualquier jornada modificada. No cambia las marcas originales, no aprueba automáticamente y respeta los períodos cerrados. La duración base de trabajo efectivo sigue siendo 8 horas.

Sin turno o con eventos incompletos, la pantalla indica que la tardanza está pendiente de cálculo. Los horarios de mañana, tarde y noche deben confirmarse con la programación de la empresa; no se deducen de la hora de llegada. Los eventos nocturnos clasificados se agrupan con la salida del día siguiente al enviarlos desde el importador.

Al confirmar un turno nocturno, también se reagrupan las jornadas ya publicadas: las marcas de madrugada pasan a la fecha de inicio y se retiran del día siguiente, que conserva su propia entrada de la noche. Se preservan fechas, eventos y procedencia originales, se registra el cambio en el historial y se exige una nueva validación. Los grupos de archivos no se mezclan. Los cierres, incidencias, ajustes y entradas contradictorias impiden la reagrupación automática para que se revisen primero; un día que queda sin marcas no se convierte automáticamente en descanso ni falta.


## Propuestas automáticas de eventos
Al pasar las marcaciones a Asistencia, las jornadas con cuatro marcas válidas y horas distintas muestran preseleccionadas entrada, salida a refrigerio, retorno y salida. Con otra cantidad se propone únicamente la primera como entrada. Se conservan las clasificaciones ya registradas. Las propuestas no modifican la fuente ni validan o aprueban el día: el usuario debe revisarlas y pulsar Confirmar eventos y validar jornada. La aprobación contable se realiza después. Para agrupar marcas sin clasificar que cruzan medianoche se requiere un horario nocturno programado; los casos ambiguos permanecen pendientes de revisión.

Para aprobar un día no laborado, Contabilidad o Gerencia debe seleccionar explícitamente la situación desde su fila. Solo Permiso exige justificación escrita. La selección y la situación anterior quedan en el historial; la aprobación conjunta no incluye estos días, que requieren confirmación individual.

## Importaciones por mes y archivo
El importador agrupa las cargas según las fechas reales de sus marcaciones. Un archivo puede figurar en varios meses; cada carga conserva su nombre, número y fecha de subida. El filtro Archivo cargado limita los códigos, Ver marcaciones y el envío a Asistencia al grupo seleccionado. El rango de envío debe pertenecer al mes indicado. Una jornada nocturna puede incluir su salida del día siguiente, incluso en el siguiente mes. Las jornadas existentes se conservan y no se duplican al reenviar.

Las exportaciones originales `.xls` se leen con `xlrd`. Si la hoja se llama `Sheet 1` o `Hoja1`, su sede se resuelve desde un nombre de archivo inequívoco (`CIX`/`Chiclayo`, `Cajamarca`, `Jaén` o `Paul Harris`); la hoja original sigue guardada como procedencia. Si no hay una sede única, se rechaza la carga sin crear asociaciones. Desde el comando `importar_zkteco` puede indicarse `--sede CHICLAYO`; las hojas con sede propia no se sobrescriben. El código biométrico se conserva como identificador del equipo, sin convertirlo en un DNI ni en una cuenta nueva.

La carga desde la web muestra etapas y avance por filas a través de una respuesta progresiva. La lectura inicial usa una barra indeterminada; el porcentaje posterior se basa en las filas procesadas y reserva el tramo final para guardar resultados. El 100 % se emite después de confirmar la transacción. Se bloquea una segunda subida mientras la primera está activa; al terminar se ofrece Ver importación. Los errores revierten la carga completa y, ante una desconexión sin confirmación, se indica revisar las cargas antes de reintentar. La respuesta JSON habitual sigue disponible para clientes que no solicitan progreso.
