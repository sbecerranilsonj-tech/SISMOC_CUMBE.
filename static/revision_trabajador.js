(() => {
    'use strict';
    const ventana = document.getElementById('detalle-jornada-dialog') || document.getElementById('revision-trabajador-dialog');
    if (!ventana) return;
    ventana.addEventListener('close', () => window.location.assign(ventana.dataset.volver));
    ventana.showModal();
    if (window.location.hash === '#detalle-jornada') {
        ventana.querySelector('#detalle-jornada')?.scrollIntoView({block: 'start'});
    }
})();

// Solo los permisos requieren una explicación escrita.
document.querySelectorAll('[data-situacion-form]').forEach(form => {
    const tipo = form.querySelector('select[name="tipo"]');
    const label = form.querySelector('[data-justificacion-permiso]');
    const motivo = label.querySelector('textarea');
    const actualizar = () => {
        const permiso = tipo.value === 'PERMISO';
        label.hidden = !permiso;
        motivo.required = permiso;
        motivo.disabled = !permiso;
    };
    tipo.addEventListener('change', actualizar);
    actualizar();
});

// Atajos de teclado: Alt + Flecha Izquierda / Derecha para navegar rápidamente
document.addEventListener('keydown', (e) => {
    if (!e.altKey) return;
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
    if (e.key === 'ArrowRight') {
        const nextDay = document.querySelector('.day-nav-group a.btn-nav-day[title*="siguiente"], .day-nav-group a.btn-nav-day[title*="Siguiente"]');
        const nextWorker = document.querySelector('.worker-nav-group a.btn-nav-trabajador[title*="siguiente"], .worker-nav-group a.btn-nav-trabajador[title*="Siguiente"]');
        const target = nextDay || nextWorker;
        if (target) {
            e.preventDefault();
            window.location.assign(target.href);
        }
    } else if (e.key === 'ArrowLeft') {
        const prevDay = document.querySelector('.day-nav-group a.btn-nav-day[title*="anterior"], .day-nav-group a.btn-nav-day[title*="Anterior"]');
        const prevWorker = document.querySelector('.worker-nav-group a.btn-nav-trabajador[title*="anterior"], .worker-nav-group a.btn-nav-trabajador[title*="Anterior"]');
        const target = prevDay || prevWorker;
        if (target) {
            e.preventDefault();
            window.location.assign(target.href);
        }
    }
});
