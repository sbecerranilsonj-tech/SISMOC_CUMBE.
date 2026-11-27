document.querySelectorAll('[data-descanso-trabajado]').forEach(form => {
    const tipo = form.querySelector('[name=tipo_descanso]');
    const contenedor = form.querySelector('[data-fecha-descanso]');
    const fecha = contenedor.querySelector('input');
    function actualizar() {
        const cambio = tipo.value === 'CAMBIO_DESCANSO';
        contenedor.hidden = !cambio;
        fecha.disabled = !cambio;
        fecha.required = cambio;
    }
    tipo.addEventListener('change', actualizar);
    actualizar();
});
