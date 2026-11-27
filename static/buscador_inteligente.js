/* Convierte los <select data-buscador-inteligente> en buscadores con sugerencias
   letra por letra. El <select> original se conserva oculto como valor seguro. */
(() => {
  const normalize = value => String(value || '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

  function setup(select) {
    if (select.dataset.buscadorListo === 'true') return;
    select.dataset.buscadorListo = 'true';

    const nombreOriginal = select.name;
    const requerido = select.required;
    const opciones = Array.from(select.options).map(opcion => ({
      value: opcion.value,
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

    const inicial = opciones.find(opcion => opcion.value === oculto.value);
    entrada.value = inicial ? inicial.nombre : '';
    estado.textContent = inicial && inicial.detalle ? inicial.detalle : '';

    let resultados = [];
    let activo = -1;
    let temporizador;

    function cerrar() {
      lista.hidden = true;
      entrada.setAttribute('aria-expanded', 'false');
      entrada.removeAttribute('aria-activedescendant');
      activo = -1;
    }

    function resaltar() {
      Array.from(lista.children).forEach((boton, indice) =>
        boton.setAttribute('aria-selected', String(indice === activo)));
      if (activo >= 0) {
        entrada.setAttribute('aria-activedescendant', lista.children[activo].id);
        lista.children[activo].scrollIntoView({block: 'nearest'});
      }
    }

    function elegir(opcion) {
      clearTimeout(temporizador);
      oculto.value = opcion.value;
      select.value = opcion.value;
      entrada.value = opcion.nombre;
      entrada.setCustomValidity('');
      estado.textContent = opcion.detalle || '';
      cerrar();
      select.dispatchEvent(new Event('change', {bubbles: true}));
    }

    function dibujar() {
      lista.replaceChildren();
      resultados.forEach((opcion, indice) => {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.id = entrada.id + '-opcion-' + indice;
        boton.setAttribute('role', 'option');
        boton.setAttribute('aria-selected', 'false');
        const fuerte = document.createElement('strong');
        fuerte.textContent = opcion.nombre;
        const detalle = document.createElement('span');
        detalle.textContent = opcion.detalle || '';
        boton.append(fuerte, detalle);
        boton.addEventListener('mousedown', evento => evento.preventDefault());
        boton.addEventListener('click', () => elegir(opcion));
        lista.append(boton);
      });
      lista.hidden = !resultados.length;
      entrada.setAttribute('aria-expanded', String(!!resultados.length));
      estado.textContent = resultados.length
        ? `Selecciona una opción de ${resultados.length} sugerencias.`
        : 'No se encontraron coincidencias. Escribe otra parte del nombre.';
      activo = -1;
    }

    function buscar() {
      const consulta = normalize(entrada.value);
      if (!consulta) {
        resultados = [];
        cerrar();
        estado.textContent = '';
        return;
      }
      const palabras = consulta.split(/\s+/);
      resultados = opciones.filter(opcion => {
        if (!opcion.value && !marcador) return false;
        const texto = normalize(opcion.nombre);
        return palabras.every(palabra => texto.includes(palabra));
      }).slice(0, 8);
      dibujar();
    }

    entrada.addEventListener('input', () => {
      oculto.value = '';
      select.value = '';
      entrada.setCustomValidity('');
      clearTimeout(temporizador);
      cerrar();
      temporizador = setTimeout(buscar, 120);
    });
    entrada.addEventListener('focus', () => {
      if (entrada.value.trim() && !oculto.value) buscar();
    });
    entrada.addEventListener('keydown', evento => {
      if (evento.key === 'Escape') { cerrar(); return; }
      if (lista.hidden || !resultados.length) return;
      if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
        evento.preventDefault();
        const paso = evento.key === 'ArrowDown' ? 1 : -1;
        activo = activo < 0
          ? (paso === 1 ? 0 : resultados.length - 1)
          : (activo + paso + resultados.length) % resultados.length;
        resaltar();
      } else if (evento.key === 'Enter') {
        evento.preventDefault();
        elegir(resultados[activo >= 0 ? activo : 0]);
      } else if (evento.key === 'Tab') {
        cerrar();
      }
    });
    entrada.addEventListener('blur', () => setTimeout(cerrar, 150));
    lista.addEventListener('mousedown', evento => evento.preventDefault());

    const formulario = select.form;
    if (formulario && requerido) {
      formulario.addEventListener('submit', evento => {
        if (oculto.value) {
          entrada.setCustomValidity('');
          return;
        }
        evento.preventDefault();
        entrada.setCustomValidity('Selecciona una opción de las sugerencias.');
        entrada.reportValidity();
        entrada.focus();
      });
    }
  }

  document.querySelectorAll('select[data-buscador-inteligente]').forEach(setup);
})();
