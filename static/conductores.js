(() => {
  const area = document.querySelector('.conductores-workspace');
  if (!area) return;
  const nombres = {importar: 'Importar itinerarios', validacion: 'Validar itinerarios', control: 'Control de conductores', catalogo: 'Conductores'};
  document.querySelectorAll('.menu-link').forEach(link => {
    const href = link.getAttribute('href');
    const activo = link.dataset.conductores
      ? link.dataset.conductores === area.dataset.seccion
      : Boolean(href && new URL(href, window.location.href).pathname === window.location.pathname);
    link.classList.toggle('active', activo);
    if (activo) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  const titulo = document.getElementById('workspace-location');
  if (titulo) titulo.textContent = nombres[area.dataset.seccion]
    || document.querySelector('.menu-link.active')?.textContent.trim()
    || area.querySelector('h1')?.textContent.trim();
  const home = document.querySelector('.account-popover a[href="?vista=dashboard"]');
  if (home) home.href = '/?vista=dashboard';
  let origen;
  const uploadForm = document.getElementById('cd-upload-directo');
  const uploadInput = document.getElementById('cd-itinerario-file');
  const uploadButton = document.querySelector('[data-upload-directo]');
  uploadButton?.addEventListener('click', () => uploadInput.click());
  uploadInput?.addEventListener('change', () => {
    if (uploadInput.files.length) uploadForm.requestSubmit();
  });
  uploadForm?.addEventListener('submit', () => {
    uploadButton.disabled = true;
    uploadButton.querySelector('span').textContent = 'Importando…';
    uploadForm.querySelector('[role="status"]').textContent = 'Procesando el reporte. Espera a que termine la importación.';
  });
  const configDialog = document.getElementById('configuracion-conductores');
  const configContenido = document.getElementById('configuracion-contenido');
  let configCambio = false;
  const editorDialog = document.getElementById('conductor-editor');
  const editorContenido = document.getElementById('conductor-editor-contenido');
  let editorOrigen;
  async function refrescarCalendario() {
    try {
      const respuesta = await fetch(window.location.href, {credentials: 'same-origin'});
      if (!respuesta.ok) return;
      const pagina = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
      const calendario = document.querySelector('.cd-calendar-scroll');
      const calendarioNuevo = pagina.querySelector('.cd-calendar-scroll');
      if (calendario && calendarioNuevo) {
        const x = calendario.scrollLeft, y = calendario.scrollTop;
        calendario.replaceChildren(...document.importNode(calendarioNuevo, true).childNodes);
        calendario.scrollLeft = x;
        calendario.scrollTop = y;
      }
      for (const selector of ['.cd-stats', '#resumen-conductores', '#salidas-por-confirmar']) {
        const actual = area.querySelector(selector), nuevo = pagina.querySelector(selector);
        if (actual && nuevo) actual.replaceWith(document.importNode(nuevo, true));
      }
    } catch { /* Se volverá a consultar al cerrar el listado. */ }
  }
  async function cargarEditor(url, opciones = {}) {
    try {
      const respuesta = await fetch(url, {credentials: 'same-origin', ...opciones, headers: {'X-Requested-With': 'XMLHttpRequest'}});
      if (!respuesta.ok) throw new Error('No se pudo cargar la ficha del conductor.');
      editorContenido.innerHTML = await respuesta.text();
      if (editorContenido.querySelector('[data-actualizado]')) {
        configCambio = true;
        await Promise.all([refrescarCalendario(), cargarConfiguracion(configDialog.dataset.url)]);
      }
    } catch (error) {
      editorContenido.textContent = error.message;
      const cerrar = document.createElement('button'); cerrar.textContent = 'Cerrar'; cerrar.className = 'cd-button'; cerrar.onclick = () => editorDialog.close(); editorContenido.append(cerrar);
    }
  }
  configDialog?.addEventListener('click', event => {
    const boton = event.target.closest('[data-editor-open]');
    if (!boton) return;
    editorOrigen = boton;
    editorContenido.textContent = 'Cargando configuración…';
    editorDialog.showModal();
    cargarEditor(boton.dataset.url);
  });
  editorDialog?.addEventListener('click', event => {if (event.target.closest('[data-close-editor]')) editorDialog.close();});
  editorDialog?.addEventListener('close', () => {if (editorOrigen?.isConnected) editorOrigen.focus();});
  editorDialog?.addEventListener('submit', event => {
    const form = event.target.closest('[data-editor-form]');
    if (!form) return;
    event.preventDefault();
    const datos = new FormData(form);
    form.querySelector('button:not([type]),button[type="submit"]')?.setAttribute('disabled', '');
    cargarEditor(form.action, {method: 'POST', body: datos});
  });
  async function cargarConfiguracion(url, opciones = {}) {
    try {
      const respuesta = await fetch(url, {credentials: 'same-origin', ...opciones, headers: {'X-Requested-With': 'XMLHttpRequest'}});
      if (!respuesta.ok) throw new Error('No se pudo abrir la configuración. Comprueba tu sesión e inténtalo nuevamente.');
      const html = await respuesta.text();
      configContenido.innerHTML = html;
      configCambio ||= !!configContenido.querySelector('[data-actualizado]');
    } catch (error) {
      configContenido.textContent = error.message;
      const cerrar = document.createElement('button');
      cerrar.textContent = 'Cerrar'; cerrar.className = 'cd-button'; cerrar.onclick = () => configDialog.close();
      configContenido.append(cerrar);
    }
  }
  document.querySelector('[data-config-open]')?.addEventListener('click', event => {
    abrir(configDialog, event.currentTarget);
    configContenido.textContent = 'Cargando conductores…';
    cargarConfiguracion(configDialog.dataset.url);
  });
  configDialog?.addEventListener('click', event => {
    if (event.target.closest('[data-close-config]')) configDialog.close();
  });
  configDialog?.addEventListener('submit', event => {
    const form = event.target.closest('[data-config-form]');
    if (!form) return;
    event.preventDefault();
    const datos = new FormData(form);
    const enviar = form.querySelector('button[type="submit"],button:not([type])');
    if (enviar) enviar.disabled = true;
    if (form.method.toLowerCase() === 'get') cargarConfiguracion(form.action + '?' + new URLSearchParams(datos));
    else cargarConfiguracion(form.action, {method: 'POST', body: datos});
  });
  configDialog?.addEventListener('close', () => {if (configCambio) window.location.reload();});
  document.getElementById('detalle-dia-dialog')?.addEventListener('click', event => {
    const verViaje = event.target.closest('[data-trip-open]');
    if (verViaje) verViaje.nextElementSibling?.showModal();
    const cerrarViaje = event.target.closest('[data-close-trip]');
    if (cerrarViaje) cerrarViaje.closest('dialog')?.close();
    const contenido = document.getElementById('detalle-dia-content');
    const editor = contenido.querySelector('[data-day-editor]');
    const editar = contenido.querySelector('[data-edit-day]');
    if (event.target.closest('[data-edit-day]') && editor) {editor.hidden = false; editar.hidden = true; editor.querySelector('select')?.focus();}
    if (event.target.closest('[data-cancel-day]') && editor) {editor.hidden = true; editar.hidden = false; editar.focus();}
  });
  document.getElementById('detalle-dia-dialog')?.addEventListener('submit', async event => {
    const form = event.target.closest('[data-day-situation]');
    if (!form) return;
    event.preventDefault();
    const boton = form.querySelector('button');
    const errores = form.querySelector('[data-day-errors]');
    const datos = new FormData(form);
    const celdaId = form.dataset.template?.replace(/^cell-/, '');
    const calendario = document.querySelector('.cd-calendar-scroll');
    const x = calendario?.scrollLeft, y = calendario?.scrollTop;
    const paginaY = window.scrollY;
    boton.disabled = true;
    errores.hidden = true;
    try {
      const respuesta = await fetch(form.action, {method: 'POST', body: datos, credentials: 'same-origin'});
      const resultado = await respuesta.json();
      if (!respuesta.ok || !resultado.ok) throw new Error((resultado.errores || ['No se pudo guardar la situación.']).join(' '));
      await refrescarCalendario();
      // El detalle actualizado se muestra al volver a seleccionar el día.
      document.getElementById('detalle-dia-dialog').close();
      requestAnimationFrame(() => {
        if (calendario) {
          calendario.scrollLeft = x;
          calendario.scrollTop = y;
        }
        window.scrollTo({top: paginaY, behavior: 'instant'});
        if (celdaId) {
          const celda = [...document.querySelectorAll('[data-cell]')]
            .find(item => item.dataset.cell === celdaId);
          celda?.focus({preventScroll: true});
        }
      });
    } catch (error) {
      errores.textContent = error.message;
      errores.hidden = false;
      boton.disabled = false;
    }
  });
  area.addEventListener('submit', async event => {
    const form = event.target.closest('[data-resolver-salida]');
    if (!form) return;
    event.preventDefault();
    const errores = form.querySelector('[data-resolver-errors]');
    const datos = new FormData(form);
    datos.set('decision', event.submitter.value);
    form.querySelectorAll('button').forEach(b => b.disabled = true);
    try {
      const respuesta = await fetch(form.action, {method: 'POST', body: datos, credentials: 'same-origin'});
      const resultado = await respuesta.json();
      if (!respuesta.ok || !resultado.ok) throw new Error((resultado.errores || ['No se pudo confirmar la salida.']).join(' '));
      await refrescarCalendario();
      const template = document.getElementById(form.dataset.template);
      form.closest('.cd-trip-popup')?.close();
      if (template) document.getElementById('detalle-dia-content').replaceChildren(template.content.cloneNode(true));
    } catch (error) {
      errores.textContent = error.message;
      errores.hidden = false;
      form.querySelectorAll('button').forEach(b => b.disabled = false);
    }
  });
  const calendarioAmpliado = document.getElementById('calendario-ampliado');
  if (area.dataset.seccion === 'control') {
    const accionesCalendario = document.createElement('div');
    accionesCalendario.className = 'cd-actions';
    accionesCalendario.style.justifyContent = 'flex-end';
    area.querySelector('.cd-calendar-scroll')?.closest('section')?.append(accionesCalendario);
    const revisar = document.createElement('button');
    revisar.type = 'button';
    revisar.className = 'cd-button';
    revisar.textContent = 'Validar todos los días';
    accionesCalendario.append(revisar);
    const dialogo = document.createElement('dialog');
    dialogo.className = 'cd-dialog';
    dialogo.setAttribute('aria-label', 'Revisión del período');
    area.append(dialogo);
    const endpoint = '/conductores/control/revision/';
    revisar.addEventListener('click', async () => {
      const periodo = area.querySelector('form[method="get"]');
      const campos = new FormData(periodo);
      const fechas = new URLSearchParams({
        desde: campos.get('desde') || '',
        hasta: campos.get('hasta') || '',
      });
      revisar.disabled = true;
      try {
        const respuesta = await fetch(`${endpoint}?${fechas}`, {credentials: 'same-origin'});
        const datos = await respuesta.json();
        if (!respuesta.ok || !datos.ok) throw new Error(datos.error || 'No se pudo revisar el período.');
        dialogo.replaceChildren();
        const titulo = document.createElement('h2');
        titulo.textContent = 'Revisión de todos los conductores';
        dialogo.append(titulo);
        const resumen = document.createElement('p');
        resumen.textContent = `Período ${campos.get('desde')} a ${campos.get('hasta')} · ${datos.conductores} conductores con actividad.`;
        dialogo.append(resumen);
        if (datos.faltantes.length) {
          const aviso = document.createElement('p');
          aviso.textContent = `Faltan ${datos.faltantes.length} días por clasificar. No se canceló ninguna salida.`;
          dialogo.append(aviso);
          const lista = document.createElement('ul');
          lista.style.cssText = 'max-height:45vh;overflow:auto;padding-left:24px';
          for (const falta of datos.faltantes) {
            const item = document.createElement('li');
            item.textContent = `${falta.conductor} · ${falta.fecha}`;
            lista.append(item);
          }
          dialogo.append(lista);
        } else if (datos.pendientes) {
          const aviso = document.createElement('p');
          aviso.textContent = `${datos.pendientes} salidas sin ventas por confirmar se marcarán como CANCELADAS. Se conservarán los reportes originales y se registrará auditoría.`;
          dialogo.append(aviso);
          const confirmar = document.createElement('button');
          confirmar.className = 'cd-button';
          confirmar.textContent = `Confirmar cancelación de ${datos.pendientes} salidas`;
          confirmar.addEventListener('click', async () => {
            if (!window.confirm(`¿Confirmas cancelar ${datos.pendientes} salidas sin ventas? Esta acción modifica su estado operativo.`)) return;
            confirmar.disabled = true;
            try {
              const cuerpo = new URLSearchParams({...Object.fromEntries(fechas), comprobante: datos.comprobante});
              const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
              const resultado = await fetch(endpoint, {method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf || ''},
                body: cuerpo});
              const respuesta = await resultado.json();
              if (!resultado.ok || !respuesta.ok) throw new Error(respuesta.error || 'No se pudieron cancelar las salidas.');
              await refrescarCalendario();
              dialogo.close();
              const notificacion = document.createElement('p');
              notificacion.className = 'cd-notice';
              notificacion.setAttribute('role', 'status');
              notificacion.textContent = `${respuesta.canceladas} salidas canceladas. Resumen actualizado.`;
              revisar.after(notificacion);
            } catch (error) {
              const aviso = document.createElement('p');
              aviso.setAttribute('role', 'alert');
              aviso.textContent = error.message;
              dialogo.append(aviso);
              confirmar.disabled = false;
            }
          });
          dialogo.append(confirmar);
        } else {
          const completo = document.createElement('p');
          completo.textContent = 'No faltan días por clasificar ni salidas sin ventas por confirmar.';
          dialogo.append(completo);
        }
        const cerrar = document.createElement('button');
        cerrar.type = 'button';
        cerrar.className = 'cd-button cd-secondary';
        cerrar.textContent = 'Cerrar';
        cerrar.addEventListener('click', () => dialogo.close());
        dialogo.append(cerrar);
        dialogo.showModal();
      } catch (error) {
        const aviso = document.createElement('p');
        aviso.setAttribute('role', 'alert');
        aviso.textContent = error.message;
        revisar.after(aviso);
      } finally {
        revisar.disabled = false;
      }
    });
  }
  let anclaCalendario;
  document.querySelector('[data-expand-calendar]')?.addEventListener('click', event => {
    const calendario = area.querySelector('.cd-calendar-scroll');
    if (!calendario || calendarioAmpliado.open) return;
    anclaCalendario = document.createComment('Ubicación del calendario');
    calendario.before(anclaCalendario);
    calendarioAmpliado.querySelector('.cd-expanded-body').append(calendario);
    abrir(calendarioAmpliado, event.currentTarget);
  });
  calendarioAmpliado?.addEventListener('close', () => {
    const calendario = calendarioAmpliado.querySelector('.cd-calendar-scroll');
    if (calendario && anclaCalendario?.isConnected) {
      const x = calendario.scrollLeft, y = calendario.scrollTop;
      anclaCalendario.replaceWith(calendario);
      calendario.scrollLeft = x; calendario.scrollTop = y;
    }
    anclaCalendario = null;
  });
  function abrir(dialog, boton) { origen = boton; dialog._returnFocus = boton; dialog.showModal(); }
  document.querySelectorAll('[data-open]').forEach(boton => boton.addEventListener('click', () => abrir(document.getElementById(boton.dataset.open), boton)));
  area.addEventListener('click', event => {
    const boton = event.target.closest('[data-cell]');
    if (!boton) return;
    const destino = document.getElementById('detalle-dia-content');
    destino.replaceChildren(document.getElementById('cell-' + boton.dataset.cell).content.cloneNode(true));
    abrir(document.getElementById('detalle-dia-dialog'), boton);
  });
  document.querySelectorAll('.cd-dialog').forEach(dialog => {
    dialog.querySelectorAll('[data-close]').forEach(boton => boton.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('close', () => {if (dialog._returnFocus?.isConnected) dialog._returnFocus.focus({preventScroll: true});});
    if (dialog.dataset.reopen) dialog.showModal();
  });
})();
