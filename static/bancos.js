(() => {
    const workspace = document.getElementById('bancos-workspace');
    if (!workspace) return;
    const paths = {importar: '/bancos/', validacion: '/bancos/validacion/', control: '/bancos/control/'};
    const names = {importar: 'Importar y validar estados BCP', control: 'Control bancario'};
    document.querySelectorAll('.menu-link').forEach(link => {
        const active = workspace.dataset.seccion === 'importar' ? (link.getAttribute('onclick') || '').includes('/bancos/') : link.getAttribute('href') === paths[workspace.dataset.seccion];
        link.classList.toggle('active', active);
        if (active) { link.setAttribute('aria-current', 'page'); link.scrollIntoView({block: 'nearest'}); }
        else link.removeAttribute('aria-current');
    });
    document.getElementById('workspace-location').textContent = names[workspace.dataset.seccion] || 'Bancos';
    const home = document.querySelector('.account-popover a[href="?vista=dashboard"]');
    if (home) home.href = '/?vista=dashboard';
    const form = document.getElementById('banco-upload-directo');
    const archivo = document.getElementById('banco-pdf-file');
    const boton = document.querySelector('[data-banco-upload]');
    boton?.addEventListener('click', () => archivo.click());
    archivo?.addEventListener('change', () => {if (archivo.files.length) form.requestSubmit();});
    form?.addEventListener('submit', () => {
        boton.disabled = true;
        boton.querySelector('span').textContent = 'Importando…';
        form.querySelector('[role="status"]').textContent = 'Procesando el estado de cuenta. Espera a que termine la importación.';
    });
})();
