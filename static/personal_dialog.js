(() => {
    const dialog = document.getElementById('ficha-personal');
    if (!dialog || dialog.tagName !== 'DIALOG') return;
    dialog.querySelector('[data-cerrar-ficha]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => {
        const r = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)) dialog.close();
    });
    dialog.addEventListener('close', () => {
        if (dialog.dataset.volverA) { window.location.assign(dialog.dataset.volverA); return; }
        const url = new URL(window.location.href);
        url.searchParams.delete('ficha');
        if (url.hash === '#ficha-personal') url.hash = '';
        history.replaceState(null, '', url);
        const enlace = document.querySelector(`.personal-directory a[href*="ficha=${dialog.dataset.trabajador}&"]`);
        if (enlace) enlace.focus({preventScroll:true});
    });
    dialog.showModal();
})();
