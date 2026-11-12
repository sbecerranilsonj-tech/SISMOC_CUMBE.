(() => {
    'use strict';
    const key = 'sismoc.theme';
    const root = document.documentElement;
    const stored = () => { try { return localStorage.getItem(key); } catch { return null; } };
    const apply = value => {
        const dark = value === 'dark';
        root.dataset.theme = dark ? 'dark' : 'light';
        root.style.colorScheme = dark ? 'dark' : 'light';
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            const label = dark ? 'Activar modo claro' : 'Activar modo oscuro';
            button.setAttribute('aria-pressed', String(dark));
            button.setAttribute('aria-label', label);
            button.title = label;
            button.querySelector('[data-theme-label]').textContent = dark ? 'Modo claro' : 'Modo oscuro';
        });
    };
    // Aplicar antes de pintar para evitar un destello blanco al volver a entrar.
    apply(stored());
    const bind = () => {
        apply(root.dataset.theme);
        document.querySelectorAll('[data-theme-toggle]').forEach(button => button.addEventListener('click', () => {
            const value = root.dataset.theme === 'dark' ? 'light' : 'dark';
            apply(value);
            try { localStorage.setItem(key, value); } catch { /* Funciona también sin almacenamiento disponible. */ }
        }));
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, { once: true });
    else bind();
    window.addEventListener('storage', event => { if (event.key === key) apply(event.newValue); });
})();
