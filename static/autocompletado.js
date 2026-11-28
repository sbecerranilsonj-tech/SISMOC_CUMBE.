/* Autocompletado reutilizable: abre/cierra sugerencias, resalta, elige y valida.
   Cada pantalla aporta cómo buscar y qué hacer al elegir; la interacción vive aquí. */
(() => {
  const normalizar = valor => String(valor || '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

  function crear({entrada, oculto, lista, estado, buscar, alElegir,
                  alLimpiar, retardo = 150, mensajeBuscando = ''}) {
    let temporizador, controlador, secuencia = 0, resultados = [], activo = -1;

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
      secuencia++;
      if (controlador) controlador.abort();
      clearTimeout(temporizador);
      oculto.value = opcion.id;
      entrada.value = opcion.nombre;
      entrada.setCustomValidity('');
      if (estado) estado.textContent = opcion.detalle || '';
      cerrar();
      if (alElegir) alElegir(opcion);
    }

    function dibujar() {
      lista.replaceChildren();
      resultados.forEach((opcion, indice) => {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.id = `${entrada.id}-opcion-${indice}`;
        boton.setAttribute('role', 'option');
        boton.setAttribute('aria-selected', 'false');
        const nombre = document.createElement('strong');
        nombre.textContent = opcion.nombre;
        const detalle = document.createElement('span');
        detalle.textContent = opcion.detalle || '';
        boton.append(nombre, detalle);
        boton.addEventListener('mousedown', evento => evento.preventDefault());
        boton.addEventListener('click', () => elegir(opcion));
        lista.append(boton);
      });
      lista.hidden = !resultados.length;
      entrada.setAttribute('aria-expanded', String(!!resultados.length));
      if (estado) {
        estado.textContent = resultados.length
          ? `Selecciona una opción de ${resultados.length} sugerencias.`
          : 'No se encontraron coincidencias. Escribe otra parte del nombre.';
      }
      activo = -1;
    }

    async function ejecutar(consulta) {
      const actual = ++secuencia;
      controlador = new AbortController();
      try {
        const encontrados = await buscar(consulta, controlador.signal);
        if (actual !== secuencia) return;
        resultados = Array.isArray(encontrados) ? encontrados : [];
        dibujar();
      } catch (error) {
        if (error.name !== 'AbortError' && actual === secuencia) {
          resultados = [];
          lista.replaceChildren();
          cerrar();
          if (estado) estado.textContent =
            'No se pudo buscar. Revisa tu sesión o conexión.';
        }
      }
    }

    entrada.addEventListener('input', () => {
      oculto.value = '';
      entrada.setCustomValidity('');
      clearTimeout(temporizador);
      if (controlador) controlador.abort();
      secuencia++;
      cerrar();
      if (alLimpiar) alLimpiar();
      const consulta = entrada.value.trim();
      if (!consulta) {
        resultados = [];
        if (estado) estado.textContent = '';
        return;
      }
      if (mensajeBuscando && estado) estado.textContent = mensajeBuscando;
      temporizador = setTimeout(() => ejecutar(consulta), retardo);
    });

    entrada.addEventListener('focus', () => {
      if (entrada.value.trim() && !oculto.value && !resultados.length) {
        entrada.dispatchEvent(new Event('input'));
      }
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

    return {cerrar, elegir, tieneValor: () => !!oculto.value};
  }

  function validar(entrada, oculto, evento,
                   mensaje = 'Selecciona una opción de las sugerencias.') {
    if (oculto.value) {
      entrada.setCustomValidity('');
      return true;
    }
    evento.preventDefault();
    entrada.setCustomValidity(mensaje);
    entrada.reportValidity();
    entrada.focus();
    return false;
  }

  window.SISMOCAutocompletado = {crear, validar, normalizar};
})();
