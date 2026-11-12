(() => {
    const input = document.getElementById('buscar-horario');
    if (!input) return;
    const opciones = JSON.parse(document.getElementById('opciones-horarios').textContent);
    const lista = document.getElementById('sugerencias-horarios');
    const hidden = document.getElementById('trabajador-consulta');
    const normalizar = valor => valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    let resultados = [], indice = -1;
    const cerrar = () => { lista.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); indice = -1; };
    const elegir = persona => { input.value = persona.label; hidden.value = persona.id; cerrar(); input.focus(); input.form.requestSubmit(); };
    function mostrar() {
        const texto = normalizar(input.value.trim());
        resultados = opciones.filter(p => !texto || normalizar(p.search + ' ' + p.label).includes(texto)).slice(0, 10);
        lista.replaceChildren(); indice = -1;
        if (!resultados.length) {
            const aviso = document.createElement('li'); aviso.textContent = 'No se encontraron trabajadores'; aviso.setAttribute('role', 'presentation'); lista.append(aviso);
        }
        resultados.forEach((persona, i) => {
            const item = document.createElement('li'); item.id = `horario-opcion-${i}`; item.setAttribute('role','option'); item.setAttribute('aria-selected','false'); item.textContent = persona.label;
            item.addEventListener('mousedown', e => e.preventDefault()); item.addEventListener('click', () => elegir(persona)); lista.append(item);
        });
        lista.hidden = false; input.setAttribute('aria-expanded','true'); input.removeAttribute('aria-activedescendant');
    }
    input.addEventListener('input', () => { hidden.value = ''; mostrar(); });
    input.addEventListener('focus', mostrar);
    input.addEventListener('blur', cerrar);
    input.addEventListener('keydown', event => {
        if (event.key === 'Escape') { cerrar(); return; }
        if (event.key === 'Enter' && indice >= 0 && !lista.hidden) { event.preventDefault(); elegir(resultados[indice]); return; }
        if (!['ArrowDown','ArrowUp'].includes(event.key)) return;
        event.preventDefault(); if (lista.hidden) mostrar(); if (!resultados.length) return;
        indice = (indice + (event.key === 'ArrowDown' ? 1 : -1) + resultados.length) % resultados.length;
        [...lista.children].forEach((item, i) => item.setAttribute('aria-selected', String(i === indice)));
        input.setAttribute('aria-activedescendant', `horario-opcion-${indice}`); lista.children[indice].scrollIntoView({block:'nearest'});
    });
})();
