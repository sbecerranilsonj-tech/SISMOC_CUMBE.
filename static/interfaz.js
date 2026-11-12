(() => {
    'use strict';
    const trigger = document.getElementById('abrir-navegacion');
    const sidebar = document.getElementById('navegacion-principal');
    const scrim = document.getElementById('cerrar-navegacion');
    if (!trigger || !sidebar || !scrim) return;
    const compact = window.matchMedia('(max-width: 900px)');
    const sync = () => {
        const open = document.body.classList.contains('sidebar-open');
        sidebar.inert = compact.matches && !open;
        trigger.setAttribute('aria-expanded', String(open));
        scrim.tabIndex = open ? 0 : -1;
    };
    const close = (restoreFocus = false) => {
        document.body.classList.remove('sidebar-open');
        sync();
        if (restoreFocus) trigger.focus();
    };
    trigger.addEventListener('click', () => {
        const opening = !document.body.classList.contains('sidebar-open');
        document.body.classList.toggle('sidebar-open', opening);
        sync();
        if (opening) sidebar.querySelector('.menu-link')?.focus();
    });
    scrim.addEventListener('click', () => close(true));
    document.addEventListener('keydown', event => {
        if (!compact.matches || !document.body.classList.contains('sidebar-open')) return;
        if (event.key === 'Escape') { event.preventDefault(); close(true); }
        if (event.key === 'Tab') {
            const focusable = [...sidebar.querySelectorAll('a[href],button:not([disabled])')];
            const first = focusable[0], last = focusable.at(-1);
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
    });
    sidebar.querySelectorAll('button.menu-link').forEach(button => button.addEventListener('click', () => close(compact.matches)));
    compact.addEventListener('change', () => close());
    sync();
})();

// Preferencias visuales locales: no alteran filtros, cálculos ni aprobaciones.
(() => {
    const read = key => { try { return localStorage.getItem(key); } catch { return null; } };
    const save = (key, value) => { try { localStorage.setItem(key, value); } catch {} };
    const collapse = document.getElementById('contraer-navegacion');
    document.querySelectorAll('.menu-link').forEach(link => {
        if (!link.getAttribute('aria-label')) link.setAttribute('aria-label', link.textContent.trim());
        link.title = link.textContent.trim();
    });
    const syncNav = collapsed => {
        document.body.classList.toggle('nav-collapsed', collapsed);
        collapse?.setAttribute('aria-expanded', String(!collapsed));
        collapse?.setAttribute('aria-label', collapsed ? 'Expandir navegación' : 'Contraer navegación');
    };
    syncNav(read('sismoc.navCollapsed') === 'true');
    collapse?.addEventListener('click', () => {
        const collapsed = !document.body.classList.contains('nav-collapsed');
        syncNav(collapsed);
        save('sismoc.navCollapsed', String(collapsed));
    });
    const density = document.getElementById('alternar-densidad');
    const syncDensity = compact => {
        document.body.classList.toggle('compact-tables', compact);
        density?.setAttribute('aria-pressed', String(compact));
    };
    syncDensity(read('sismoc.compactTables') === 'true');
    density?.addEventListener('click', () => {
        const compact = !document.body.classList.contains('compact-tables');
        syncDensity(compact);
        save('sismoc.compactTables', String(compact));
    });
    const filterToggle = document.getElementById('alternar-filtros');
    const filters = document.getElementById('filtros-asistencia');
    filterToggle?.addEventListener('click', () => {
        filters.hidden = !filters.hidden;
        filterToggle.setAttribute('aria-expanded', String(!filters.hidden));
    });
})();

// El menú de cuenta se cierra al salir del control o al pulsar Escape.
(() => {
    const account = document.querySelector('.account-menu');
    if (!account) return;
    document.addEventListener('click', event => {
        if (!account.contains(event.target)) account.open = false;
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && account.open) {
            account.open = false;
            account.querySelector('summary').focus();
        }
    });
})();

// Solo el saludo de inicio de sesión caduca; los demás avisos siguen visibles.
document.querySelectorAll('.app-alert[data-auto-dismiss]').forEach(alert => {
    window.setTimeout(() => {
        const container = alert.parentElement;
        alert.remove();
        if (container && !container.children.length) container.remove();
    }, Number(alert.dataset.autoDismiss));
});
