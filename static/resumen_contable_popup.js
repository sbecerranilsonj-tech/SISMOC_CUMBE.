(() => {
    const dialog = document.getElementById('resumen-contable-popup');
    if (!dialog) return;
    let trigger;
    const open = button => { trigger = button; if (!dialog.open) dialog.showModal(); };
    document.querySelectorAll('[data-abrir-resumen-contable]').forEach(button => button.addEventListener('click', () => open(button)));
    dialog.querySelector('[data-cerrar-resumen-contable]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => {
        if (event.target !== dialog) return;
        const box = dialog.getBoundingClientRect();
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    });
    dialog.addEventListener('close', () => {
        document.body.classList.remove('resumen-contable-abierto');
        const url = new URL(location.href);
        url.searchParams.delete('resumen_contable');
        history.replaceState(null, '', url);
        trigger?.focus();
    });
    dialog.addEventListener('toggle', () => document.body.classList.toggle('resumen-contable-abierto', dialog.open));
    if (new URLSearchParams(location.search).get('resumen_contable') === '1') open(document.querySelector('[data-abrir-resumen-contable]'));
})();
