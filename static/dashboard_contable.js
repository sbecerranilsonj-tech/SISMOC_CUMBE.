(() => {
    const buttons = [...document.querySelectorAll('[data-priority-filter]')];
    const rows = [...document.querySelectorAll('[data-priority-row]')];
    const status = document.querySelector('[data-priority-status]');
    const empty = document.querySelector('[data-priority-empty]');
    const reset = document.querySelector('[data-priority-filter="todos"]');
    if (!status || !empty) return;
    buttons.forEach(button => button.addEventListener('click', () => {
        const filter = button.dataset.priorityFilter;
        let found = 0;
        rows.forEach(row => {
            const matches = filter === 'todos' || Number(row.getAttribute(`data-${filter}`)) > 0;
            row.hidden = !matches || found >= 10;
            if (matches) found++;
        });
        buttons.forEach(b => {
            if (b !== reset) b.setAttribute('aria-pressed', String(b === button));
        });
        reset.hidden = filter === 'todos';
        document.querySelector('[data-priority-default-empty]')?.toggleAttribute('hidden', filter !== 'todos');
        empty.hidden = found > 0 || (filter === 'todos' && rows.length === 0);
        const label = {todos: 'Todos los pendientes', 'por-validar': 'Por validar', listas: 'Listas para aprobar'}[filter];
        status.textContent = `${label} · ${found} ${found === 1 ? 'trabajador' : 'trabajadores'}${found > 10 ? ' · Primeros 10' : ''}`;
        document.getElementById('contable-pendientes')?.scrollIntoView({block: 'nearest', behavior: 'instant'});
    }));
})();
