// Consultar solo registros recibidos: este refresco no accede al hardware.
let huelleroActivo = false;
let temporizadorHuellero = null;
let consultaHuelleroEnCurso = false;

function activarHuellero(activo) {
    huelleroActivo = activo;
    clearTimeout(temporizadorHuellero);
    if (activo && !document.hidden) actualizarRegistrosHuellero();
}

async function actualizarRegistrosHuellero() {
    if (consultaHuelleroEnCurso) return;
    const contenedor = document.getElementById('registroHuellero');
    if (!contenedor) return;
    consultaHuelleroEnCurso = true;
    clearTimeout(temporizadorHuellero);
    const boton = document.getElementById('btnActualizarHuellero');
    const error = document.getElementById('errorRegistrosHuellero');
    boton.disabled = true;
    try {
        const respuesta = await fetch(contenedor.dataset.url, {cache: 'no-store'});
        if (respuesta.redirected || respuesta.status === 401 || respuesta.status === 403) {
            huelleroActivo = false;
            throw new Error('La sesión no permite consultar los registros. Ingrese nuevamente al sistema.');
        }
        if (!respuesta.ok) throw new Error('No se pudo actualizar la lista. Se conservan los últimos registros visibles.');
        const datos = await respuesta.json();
        const cuerpo = document.querySelector('#tablaZkLive tbody');
        const filas = document.createDocumentFragment();
        for (const registro of datos.registros) {
            const fila = document.createElement('tr');
            for (const campo of ['fecha_hora', 'dni', 'nombre', 'evento', 'sede', 'equipo', 'id_biometrico']) {
                const celda = document.createElement('td');
                celda.textContent = registro[campo];
                fila.appendChild(celda);
            }
            filas.appendChild(fila);
        }
        if (!datos.registros.length) {
            const fila = document.createElement('tr');
            const celda = document.createElement('td');
            celda.colSpan = 7;
            celda.className = 'estado-vacio';
            celda.textContent = 'No hay marcaciones recibidas del huellero para hoy.';
            fila.appendChild(celda);
            filas.appendChild(fila);
        }
        cuerpo.replaceChildren(filas);
        document.getElementById('conteoRegistrosHuellero').textContent = datos.total + ' marcaciones de hoy · Mostrando ' + datos.registros.length + ' de ' + datos.total;
        document.getElementById('actualizacionHuellero').textContent = 'Última lectura de registros: ' + datos.actualizado;
        error.hidden = true;
    } catch (fallo) {
        error.textContent = fallo.message || 'No se pudo actualizar la lista de marcaciones.';
        error.hidden = false;
    } finally {
        consultaHuelleroEnCurso = false;
        boton.disabled = false;
        if (huelleroActivo && !document.hidden) temporizadorHuellero = setTimeout(actualizarRegistrosHuellero, 10000);
    }
}

document.addEventListener('visibilitychange', () => {
    clearTimeout(temporizadorHuellero);
    if (huelleroActivo && !document.hidden) actualizarRegistrosHuellero();
});
