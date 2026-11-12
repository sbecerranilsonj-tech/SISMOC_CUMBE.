(() => {
    'use strict';
    const detalle = document.getElementById('detalle-jornada');
    const manual = detalle?.querySelector('.formulario-marcacion-manual');
    const clasificacion = detalle?.querySelector('.correcciones-cuadro-excel');
    if (!manual || !clasificacion) return;
    manual.addEventListener('submit', () => {
        manual.querySelectorAll('[data-evento-copiado]').forEach(campo => campo.remove());
        for (const [nombre, valor] of new FormData(clasificacion)) {
            if (!/^(evento|original)_\d+$/.test(nombre)) continue;
            const campo = document.createElement('input');
            campo.type = 'hidden'; campo.name = nombre; campo.value = valor;
            campo.dataset.eventoCopiado = 'true';
            manual.appendChild(campo);
        }
    });
})();

// Ventana independiente: cancelar conserva los cambios del cuadro diario.
(() => {
    const dialog = document.getElementById('marcacion-manual-dialog');
    const open = document.getElementById('abrir-marcacion-manual');
    if (!dialog || !open) return;
    const form = dialog.querySelector('form');
    const title = dialog.querySelector('#titulo-marcacion-manual');
    const submit = form.querySelector('button[type="submit"]');
    open.addEventListener('click', () => {
        form.reset();
        form.elements.accion.value = 'marcacion_manual';
        form.elements.marcacion_id.value = '';
        title.textContent = 'Agregar marcación manual';
        submit.textContent = 'Guardar marcación manual y validar';
        if (!dialog.open) dialog.showModal();
    });
    document.querySelectorAll('[data-editar-manual]').forEach(button => {
        button.addEventListener('click', () => {
            form.reset();
            form.elements.accion.value = 'editar_marcacion_manual';
            form.elements.marcacion_id.value = button.dataset.editarManual;
            form.elements.fecha_manual.value = button.dataset.fecha;
            form.elements.hora_manual.value = button.dataset.hora;
            form.elements.tipo_evento_manual.value = button.dataset.evento;
            form.elements.motivo_manual.value = button.dataset.motivo;
            title.textContent = 'Editar marcación manual';
            submit.textContent = 'Guardar cambios y validar';
            dialog.showModal();
        });
    });
    dialog.querySelectorAll('[data-cerrar-manual]').forEach(button => {
        button.addEventListener('click', () => dialog.close());
    });
    dialog.addEventListener('close', () => open.focus());
})();

// La fecha de una salida de madrugada debe quedar visible antes de guardar.
(() => {
    const form = document.querySelector('.formulario-marcacion-manual');
    if (!form || form.dataset.turnoNocturno !== 'si') return;
    const fecha = form.elements.fecha_manual, hora = form.elements.hora_manual;
    const tipo = form.elements.tipo_evento_manual, aviso = form.querySelector('[data-fecha-nocturna]');
    let fechaElegida = false;
    fecha.addEventListener('change', () => { fechaElegida = true; aviso.hidden = true; });
    form.addEventListener('reset', () => { fechaElegida = false; aviso.hidden = true; });
    const actualizar = () => {
        if (fechaElegida || form.elements.accion.value !== 'marcacion_manual' || !hora.value || !form.dataset.horaEntrada) return;
        const siguiente = tipo.value !== 'ENTRADA' && hora.value < form.dataset.horaEntrada;
        const dia = new Date(form.dataset.fechaJornada + 'T12:00:00Z');
        if (siguiente) dia.setUTCDate(dia.getUTCDate() + 1);
        fecha.value = dia.toISOString().slice(0,10);
        aviso.hidden = !siguiente;
        aviso.textContent = siguiente ? 'Marcación del día siguiente: ' + fecha.value.split('-').reverse().join('/') + '.' : '';
    };
    hora.addEventListener('input', actualizar);
    tipo.addEventListener('change', actualizar);
})();
