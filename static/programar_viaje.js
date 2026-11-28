(() => {
  const {crear, validar} = window.SISMOCAutocompletado;
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

    crear({
      entrada: input, oculto: hidden, lista: menu, estado: status,
      retardo: 180, mensajeBuscando: 'Buscando…',
      buscar: async (consulta, señal) => {
        const url = new URL(base, location.href);
        url.searchParams.set('tipo', picker.dataset.tipo);
        url.searchParams.set('q', consulta);
        const response = await fetch(url, {
          signal: señal, credentials: 'same-origin', cache: 'no-store',
        });
        if (response.redirected) throw new Error('sesion');
        if (!response.ok) throw new Error(`estado ${response.status}`);
        const data = await response.json();
        return Array.isArray(data.resultados) ? data.resultados : [];
      },
    });
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
        if (!validar(input, hidden, event)) return;
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
