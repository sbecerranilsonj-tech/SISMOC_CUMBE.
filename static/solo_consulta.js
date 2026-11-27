// Presentación de solo lectura. La seguridad real se aplica también en servidor.
(() => {
    if (!document.body.classList.contains('solo-consulta')) return;
    const escritura = form => form && !['get', 'dialog'].includes(form.method.toLowerCase())
        && new URL(form.action, location.href).pathname !== '/logout/';
    const aplicar = () => {
        document.querySelectorAll('form').forEach(form => {
            if (!escritura(form)) return;
            if (!form.hasAttribute('data-consulta-bloqueado')) {
                form.setAttribute('data-consulta-bloqueado', 'true');
                form.addEventListener('submit', event => {
                    event.preventDefault();
                    event.stopImmediatePropagation();
                }, true);
            }
            [...form.elements].forEach(control => {
                if (control.matches('input,select,textarea') && !control.disabled) {
                    control.disabled = true;
                }
                if (control.matches('button,input[type="submit"]')
                    && !/^(cerrar|cancelar|volver)$/i.test(control.textContent.trim())
                    && !control.hasAttribute('data-solo-edicion')) {
                    control.setAttribute('data-solo-edicion', 'true');
                }
            });
        });
        // Acciones externas al formulario (popups de alta/edición y huellero).
        document.querySelectorAll('button[onclick],a[onclick],button[data-rule-popup]').forEach(control => {
            if (/abrirConfigHuellero|consultarConexionEquipo|consultarHuellero|sincronizar/i.test(control.getAttribute('onclick') || '')
                && !control.hasAttribute('data-solo-edicion')) {
                control.setAttribute('data-solo-edicion', 'true');
            }
        });
    };
    aplicar();
    new MutationObserver(aplicar).observe(document.body, {
        childList: true, subtree: true, attributes: true,
        attributeFilter: ['disabled', 'method', 'formmethod'],
    });
})();
