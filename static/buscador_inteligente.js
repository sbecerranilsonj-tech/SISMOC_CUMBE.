/* Convierte los <select data-buscador-inteligente> en buscadores con sugerencias
   letra por letra. El <select> original se conserva oculto como valor seguro. */
(() => {
  const {crear, validar, normalizar} = window.SISMOCAutocompletado;

  function setup(select) {
    if (select.dataset.buscadorListo === 'true') return;
    select.dataset.buscadorListo = 'true';

    const nombreOriginal = select.name;
    const requerido = select.required;
    const opciones = Array.from(select.options).map(opcion => ({
      id: opcion.value,
      nombre: opcion.textContent.trim(),
      detalle: opcion.dataset.detalle || '',
    }));
    const marcador = select.dataset.buscadorIncluirVacio !== 'false';

    const contenedor = document.createElement('div');
    contenedor.className = 'bus-inteligente';
    contenedor.dataset.tipo = select.dataset.buscadorTipo || '';

    const entrada = document.createElement('input');
    entrada.type = 'search';
    entrada.id = (select.id || ('buscador-' + nombreOriginal)) + '-buscar';
    entrada.removeAttribute('name');
    entrada.placeholder = select.dataset.buscadorPlaceholder || 'Escribe para buscar…';
    entrada.autocomplete = 'off';
    entrada.setAttribute('role', 'combobox');
    entrada.setAttribute('aria-autocomplete', 'list');
    entrada.setAttribute('aria-expanded', 'false');
    entrada.required = false;

    const oculto = document.createElement('input');
    oculto.type = 'hidden';
    oculto.name = nombreOriginal;
    oculto.value = select.value;
    oculto.dataset.buscadorValor = 'true';

    const lista = document.createElement('div');
    lista.className = 'bus-inteligente-opciones';
    lista.id = entrada.id + '-opciones';
    lista.setAttribute('role', 'listbox');
    lista.setAttribute('aria-label', 'Sugerencias');
    lista.hidden = true;
    entrada.setAttribute('aria-controls', lista.id);

    const estado = document.createElement('small');
    estado.setAttribute('aria-live', 'polite');
    estado.dataset.buscadorEstado = 'true';

    contenedor.append(entrada, oculto, lista, estado);
    select.after(contenedor);
    select.hidden = true;
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    select.removeAttribute('name');
    select.required = false;

    const etiqueta = document.querySelector('label[for="' + select.id + '"]');
    if (etiqueta) etiqueta.htmlFor = entrada.id;

    const inicial = opciones.find(opcion => opcion.id === oculto.value);
    entrada.value = inicial ? inicial.nombre : '';
    estado.textContent = inicial && inicial.detalle ? inicial.detalle : '';

    crear({
      entrada, oculto, lista, estado,
      retardo: 120,
      buscar: async consulta => {
        const palabras = normalizar(consulta).split(/\s+/);
        return opciones.filter(opcion => {
          if (!opcion.id && !marcador) return false;
          return palabras.every(palabra => normalizar(opcion.nombre).includes(palabra));
        }).slice(0, 8);
      },
      alElegir: opcion => {
        select.value = opcion.id;
        select.dispatchEvent(new Event('change', {bubbles: true}));
      },
      alLimpiar: () => { select.value = ''; },
    });

    const formulario = select.form;
    if (formulario && requerido) {
      formulario.addEventListener('submit', evento =>
        validar(entrada, oculto, evento));
    }
  }

  document.querySelectorAll('select[data-buscador-inteligente]').forEach(setup);
})();
