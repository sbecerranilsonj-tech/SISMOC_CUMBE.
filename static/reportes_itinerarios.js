(() => {
    const dialogo = document.getElementById('reportes-itinerarios-dialog');
    const boton = document.querySelector('[data-abrir-reportes]');
    if (!dialogo || !boton) return;
    boton.addEventListener('click', () => {
        if (!dialogo.open) dialogo.showModal();
    });
    dialogo.querySelector('[data-cerrar-reportes]')?.addEventListener('click', () => dialogo.close());
    dialogo.addEventListener('close', () => boton.focus({preventScroll: true}));
})();
