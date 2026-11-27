(() => {
    const input = document.querySelector('[data-sugerir-codigos]');
    if (!input) return;
    const form = input.form;
    const list = document.getElementById(input.getAttribute('aria-controls'));
    let timer, controller, active = -1;
    function close() {
        list.hidden = true;
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
        active = -1;
    }
    function show() { list.hidden = false; input.setAttribute('aria-expanded', 'true'); }
    function message(text) {
        list.replaceChildren();
        const item = document.createElement('span');
        item.className = 'codigo-sugerencia-estado';
        item.setAttribute('role', 'status');
        item.textContent = text;
        list.appendChild(item); show();
    }
    function search() {
        clearTimeout(timer);
        if (controller) controller.abort();
        close(); list.replaceChildren();
        const query = input.value.trim();
        if (!query) return;
        timer = setTimeout(async () => {
            const params = new URLSearchParams(new FormData(form));
            params.set('q', query);
            params.delete('filtro_codigo');
            const snapshot = params.toString();
            controller = new AbortController();
            message('Buscando códigos…');
            try {
                const response = await fetch(input.dataset.sugerirCodigos + '?' + snapshot, {signal:controller.signal, headers:{Accept:'application/json'}});
                if (!response.ok || response.redirected) throw new Error('No se pudieron consultar los códigos. Usa Buscar para continuar.');
                const data = await response.json();
                const current = new URLSearchParams(new FormData(form));
                current.set('q', input.value.trim()); current.delete('filtro_codigo');
                if (current.toString() !== snapshot) return;
                list.replaceChildren();
                if (!data.resultados.length) { message('No hay códigos coincidentes en estos filtros.'); return; }
                data.resultados.forEach((item, index) => {
                    const option = document.createElement('button');
                    option.type = 'button'; option.className = 'codigo-sugerencia'; option.tabIndex = -1;
                    option.id = 'codigo-sugerencia-' + index;
                    option.setAttribute('role','option'); option.setAttribute('aria-selected','false');
                    const code = document.createElement('strong'); code.textContent = item.codigo;
                    const name = document.createElement('span'); name.textContent = item.nombre || 'Nombre por completar';
                    const origin = document.createElement('small'); origin.textContent = item.sede + ' · Equipo ' + (item.equipo || 'sin indicar');
                    option.append(code, name, origin);
                    option.addEventListener('mousedown', event => event.preventDefault());
                    option.addEventListener('click', () => { input.value = item.codigo; close(); form.requestSubmit(); });
                    list.appendChild(option);
                });
                show();
            } catch (error) { if (error.name !== 'AbortError') message(error.message); }
        }, 220);
    }
    input.addEventListener('input', search);
    input.addEventListener('keydown', event => {
        if (event.key === 'Escape') { clearTimeout(timer); if (controller) controller.abort(); close(); return; }
        if (list.hidden) return;
        const options = [...list.querySelectorAll('[role=option]')];
        if (event.key === 'Enter' && active >= 0) { event.preventDefault(); options[active].click(); return; }
        if (!['ArrowDown','ArrowUp'].includes(event.key) || !options.length) return;
        event.preventDefault();
        active = (active + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
        options.forEach((option, index) => option.setAttribute('aria-selected', String(index === active)));
        input.setAttribute('aria-activedescendant', options[active].id);
        options[active].scrollIntoView({block:'nearest'});
    });
    input.addEventListener('blur', () => { clearTimeout(timer); if (controller) controller.abort(); close(); });
    form.addEventListener('change', event => { if (event.target !== input) { if (controller) controller.abort(); clearTimeout(timer); close(); } });
    form.addEventListener('submit', close);
})();
