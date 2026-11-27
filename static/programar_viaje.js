(() => {
  const dialogs = [...document.querySelectorAll('.bus-programar-dialog')];
  if (!dialogs.length) return;
  const base = dialogs[0].dataset.sugerenciasUrl || '/movil/buses/sugerencias/';

  function setup(picker) {
    if (picker.dataset.programarListo === 'true') return;
    const input = picker.querySelector('[data-programar-input]');
    const hidden = picker.querySelector('[data-programar-valor]');
    const menu = picker.querySelector('[data-programar-opciones]');
    const status = picker.querySelector('[data-programar-estado]');
    if (!input || !hidden || !menu) return;
    picker.dataset.programarListo = 'true';

    const tipo = picker.dataset.tipo;
    let timer, controller, sequence = 0, results = [], active = -1;

    function close() {
      menu.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      active = -1;
    }

    function highlight() {
      [...menu.children].forEach((button, index) => {
        button.setAttribute('aria-selected', String(index === active));
      });
      if (active >= 0) {
        input.setAttribute('aria-activedescendant', menu.children[active].id);
        menu.children[active].scrollIntoView({block: 'nearest'});
      }
    }

    function choose(item) {
      sequence++;
      if (controller) controller.abort();
      clearTimeout(timer);
      hidden.value = item.id;
      input.value = item.nombre;
      input.setCustomValidity('');
      status.textContent = item.detalle || '';
      close();
    }

    function render() {
      menu.replaceChildren();
      results.forEach((item, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.id = `${input.id}-opcion-${index}`;
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', 'false');
        button.dataset.id = item.id;
        const name = document.createElement('strong');
        name.textContent = item.nombre;
        const detail = document.createElement('span');
        detail.textContent = item.detalle || '';
        button.append(name, detail);
        button.addEventListener('mousedown', event => event.preventDefault());
        button.addEventListener('click', () => choose(item));
        menu.append(button);
      });
      menu.hidden = !results.length;
      input.setAttribute('aria-expanded', String(!!results.length));
      status.textContent = results.length
        ? `Selecciona una opción de ${results.length} sugerencias.`
        : 'No se encontraron coincidencias. Escribe otra parte del nombre.';
      active = -1;
    }

    async function buscar(consulta) {
      const current = ++sequence;
      controller = new AbortController();
      try {
        const url = new URL(base, location.href);
        url.searchParams.set('tipo', tipo);
        url.searchParams.set('q', consulta);
        const response = await fetch(url, {
          signal: controller.signal,
          credentials: 'same-origin',
          cache: 'no-store',
        });
        if (response.redirected) throw new Error('sesion');
        if (!response.ok) throw new Error(`estado ${response.status}`);
        const data = await response.json();
        if (current !== sequence) return;
        results = Array.isArray(data.resultados) ? data.resultados : [];
        render();
      } catch (error) {
        if (error.name !== 'AbortError' && current === sequence) {
          results = [];
          menu.replaceChildren();
          close();
          status.textContent = 'No se pudo buscar. Revisa tu sesión o conexión.';
        }
      }
    }

    input.addEventListener('input', () => {
      hidden.value = '';
      input.setCustomValidity('');
      clearTimeout(timer);
      if (controller) controller.abort();
      sequence++;
      close();
      const consulta = input.value.trim();
      if (!consulta) {
        results = [];
        status.textContent = '';
        return;
      }
      status.textContent = 'Buscando…';
      timer = setTimeout(() => buscar(consulta), 180);
    });

    input.addEventListener('focus', () => {
      if (input.value.trim() && !hidden.value && !results.length) {
        input.dispatchEvent(new Event('input'));
      }
    });

    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        close();
        return;
      }
      if (menu.hidden || !results.length) return;
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const step = event.key === 'ArrowDown' ? 1 : -1;
        active = active < 0
          ? (step === 1 ? 0 : results.length - 1)
          : (active + step + results.length) % results.length;
        highlight();
      } else if (event.key === 'Enter') {
        event.preventDefault();
        choose(results[active >= 0 ? active : 0]);
      } else if (event.key === 'Tab') {
        close();
      }
    });

    input.addEventListener('blur', () => setTimeout(close, 150));
    menu.addEventListener('mousedown', event => event.preventDefault());
  }

  dialogs.forEach(dialog => {
    const pickers = [...dialog.querySelectorAll('[data-programar-picker]')];
    pickers.forEach(setup);

    dialog.querySelectorAll('[data-programar-cerrar]').forEach(button => {
      button.addEventListener('click', () => dialog.close());
    });

    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });

    const form = dialog.querySelector('form');
    form?.addEventListener('submit', event => {
      for (const picker of pickers) {
        const input = picker.querySelector('[data-programar-input]');
        const hidden = picker.querySelector('[data-programar-valor]');
        if (!input || !hidden) continue;
        if (hidden.value) {
          input.setCustomValidity('');
          continue;
        }
        event.preventDefault();
        input.setCustomValidity('Selecciona una opción de las sugerencias.');
        input.reportValidity();
        input.focus();
        return;
      }
    });
  });

  [[document.querySelectorAll('[data-programar-abrir]'), 'programar-viaje'],
   [document.querySelectorAll('[data-editar-abrir]'), 'editar-viaje']].forEach(([buttons, id]) => {
    buttons.forEach(button => {
      button.addEventListener('click', () => {
        const dialog = document.getElementById(id);
        if (!dialog || dialog.open) return;
        dialog.showModal();
        dialog.querySelector('[data-programar-input]')?.focus();
      });
    });
  });
})();
