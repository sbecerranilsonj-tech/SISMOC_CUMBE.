(() => {
    'use strict';
    const dialogo = document.getElementById('registro-trabajador-dialog');
    const registro = document.getElementById('registro-trabajador-form');
    if (!dialogo || !registro) return;
    let origen = null;
    let conflicto = null;
    const panelConflicto = document.getElementById('conflicto-ficha-trabajador');
    const botonCorregir = document.getElementById('usar-ficha-existente');
    function limpiarConflicto() {
        conflicto = null; panelConflicto.hidden = true;
        registro.querySelector('[type=submit]').hidden = false;
    }
    const mostrarError = (elemento, texto) => { elemento.textContent = texto; elemento.hidden = !texto; };
    async function guardar(formulario, url, extras = {}) {
        const cuerpo = new FormData(formulario);
        Object.entries(extras).forEach(([clave, valor]) => cuerpo.set(clave, valor));
        const respuesta = await fetch(url, { method: 'POST', body: cuerpo, headers: { 'X-CSRFToken': formulario.querySelector('[name=csrfmiddlewaretoken]').value, 'Accept': 'application/json' } });
        if (respuesta.redirected) throw new Error('La sesión terminó. Recargue la página e ingrese de nuevo.');
        const datos = await respuesta.json();
        if (!respuesta.ok) {
            if (formulario === registro && datos.conflicto) {
                conflicto = datos.conflicto;
                const destino = conflicto.destino;
                document.getElementById('datos-ficha-existente').textContent = `Ficha encontrada: ${destino.nombre} · DNI ${destino.dni} · Área: ${destino.area}. Códigos de la ficha a corregir: ${conflicto.codigos}.`;
                panelConflicto.hidden = false;
                botonCorregir.hidden = !conflicto.puede_unir;
                registro.querySelector('[type=submit]').hidden = conflicto.puede_unir;
                if (!conflicto.puede_unir) document.getElementById('datos-ficha-existente').textContent += ' La ficha actual tiene una cuenta de acceso y requiere revisión administrativa; las cuentas no se unen desde aquí.';
                panelConflicto.scrollIntoView({block: 'nearest', behavior: 'smooth'});
                if (conflicto.puede_unir) botonCorregir.focus({preventScroll: true});
            }
            const errores = datos.errores ? Object.values(datos.errores).flat().join(' ') : '';
            throw new Error(errores || datos.detail || 'No se pudo guardar. Inténtelo de nuevo.');
        }
        window.location.reload();
    }
    document.querySelectorAll('.buscador-trabajador').forEach(formulario => {
        const entrada = formulario.querySelector('.consulta-trabajador');
        const resultados = formulario.querySelector('.resultados-trabajador');
        const elegido = formulario.querySelector('[name=trabajador]');
        const confirmar = formulario.querySelector('.confirmar-trabajador');
        const crear = formulario.querySelector('.abrir-registro-trabajador');
        const editar = formulario.querySelector('.editar-seleccionado');
        const datosImportados = {nombres: '', apellidoPaterno: '', apellidoMaterno: '', ...editar.dataset};
        const seleccion = formulario.querySelector('.seleccion-trabajador');
        const error = formulario.querySelector('.error-trabajador');
        let espera, controlador;
        entrada.addEventListener('input', () => {
            clearTimeout(espera);
            if (controlador) controlador.abort();
            resultados.replaceChildren(); elegido.value = ''; confirmar.disabled = true; seleccion.textContent = '';
            Object.assign(editar.dataset, datosImportados);
            editar.title = 'Editar y completar los datos importados';
            mostrarError(error, '');
            const consulta = entrada.value.trim();
            if (consulta.length < 2) return;
            espera = setTimeout(async () => {
                controlador = new AbortController();
                resultados.textContent = 'Buscando…';
                try {
                    const respuesta = await fetch(formulario.dataset.buscar + '?q=' + encodeURIComponent(consulta), { signal: controlador.signal });
                    if (!respuesta.ok || respuesta.redirected) throw new Error('No se pudo consultar. Revise su sesión e intente de nuevo.');
                    const datos = await respuesta.json();
                    if (entrada.value.trim() !== consulta) return;
                    resultados.replaceChildren();
                    if (!datos.resultados.length) {
                        resultados.textContent = 'No se encontró al trabajador.';
                        crear.hidden = false;
                    }
                    datos.resultados.forEach(t => {
                        const boton = document.createElement('button');
                        boton.type = 'button'; boton.className = 'resultado-ficha btn-dark-outline';
                        boton.textContent = `${t.nombre} · DNI ${t.dni} · ${t.codigo} · Área: ${t.area}`;
                        boton.addEventListener('click', () => {
                            elegido.value = t.id; confirmar.disabled = false;
                            Object.assign(editar.dataset, {url:t.url_editar,nombre:t.nombre_completo,nombres:t.nombres,apellidoPaterno:t.apellido_paterno,apellidoMaterno:t.apellido_materno,dni:t.dni,area:t.area,pendiente:'no'});
                            editar.disabled = false;
                            editar.title = 'Editar la ficha de ' + t.nombre;
                            seleccion.textContent = `Seleccionado: ${t.nombre} · DNI ${t.dni} · ${t.codigo} · Área: ${t.area}`;
                            resultados.replaceChildren();
                        });
                        resultados.appendChild(boton);
                    });
                } catch (exc) {
                    if (exc.name !== 'AbortError') { resultados.replaceChildren(); mostrarError(error, exc.message); }
                }
            }, 300);
        });
        formulario.addEventListener('submit', async evento => {
            evento.preventDefault();
            if (!elegido.value) return;
            confirmar.disabled = true;
            try { await guardar(formulario, formulario.action); }
            catch (exc) { mostrarError(error, exc.message); confirmar.disabled = false; }
        });
        crear.addEventListener('click', () => {
            limpiarConflicto();
            origen = formulario; registro.reset(); registro.action = formulario.dataset.registrar;
            document.getElementById('titulo-registro-trabajador').textContent = 'Registrar trabajador';
            document.getElementById('descripcion-registro-trabajador').textContent = 'Se guardará su ficha de personal y se vinculará al código seleccionado. No se creará una cuenta de acceso.';
            registro.querySelector('[type=submit]').textContent = 'Guardar y vincular';
            document.getElementById('codigo-importado-registro').value = formulario.dataset.codigo;
            const consulta = entrada.value.trim();
            if (/^[0-9]{8}$/.test(consulta)) registro.elements.dni.value = consulta;
            document.getElementById('nombre-anterior-trabajador').hidden = true;
            mostrarError(registro.querySelector('.error-registro-trabajador'), '');
            dialogo.showModal();
        });
    });
    document.querySelectorAll('.editar-trabajador').forEach(boton => {
        boton.addEventListener('click', () => {
            limpiarConflicto();
            origen = boton; registro.reset(); registro.action = boton.dataset.url;
            const pendiente = boton.dataset.pendiente === 'si';
            document.getElementById('titulo-registro-trabajador').textContent = 'Editar trabajador';
            document.getElementById('descripcion-registro-trabajador').textContent = pendiente
                ? 'Complete el nombre importado, DNI y área para guardar la ficha y vincularla a este código. Si ya tiene ficha, búsquela y selecciónela para editarla.'
                : 'Los cambios se guardarán en su ficha de personal y se mostrarán en los códigos vinculados a este trabajador.';
            document.getElementById('codigo-importado-registro').value = boton.dataset.codigo;
            registro.elements.nombres.value = boton.dataset.nombres || '';
            registro.elements.apellido_paterno.value = boton.dataset.apellidoPaterno || '';
            registro.elements.apellido_materno.value = boton.dataset.apellidoMaterno || '';
            const anterior = document.getElementById('nombre-anterior-trabajador');
            anterior.textContent = 'Nombre registrado anteriormente: ' + (boton.dataset.nombre || '') + '. Complete los campos por separado.';
            anterior.hidden = Boolean(boton.dataset.nombres) || !boton.dataset.nombre || boton.dataset.nombre === boton.dataset.codigo;
            registro.elements.dni.value = boton.dataset.dni;
            registro.elements.area.value = boton.dataset.area;
            registro.querySelector('[type=submit]').textContent = pendiente ? 'Guardar y vincular' : 'Guardar cambios';
            mostrarError(registro.querySelector('.error-registro-trabajador'), '');
            dialogo.showModal();
        });
    });
    registro.querySelector('.cancelar-registro-trabajador').addEventListener('click', () => dialogo.close());
    registro.addEventListener('input', limpiarConflicto);
    botonCorregir.addEventListener('click', async () => {
        if (!conflicto) return;
        const datos = conflicto;
        botonCorregir.disabled = true;
        const guardarNormal = registro.querySelector('[type=submit]'); guardarNormal.disabled = true;
        try { await guardar(registro, registro.action, {usar_existente: '1', destino_id: String(datos.destino.id), origen_id: String(datos.origen_id)}); }
        catch (exc) { mostrarError(registro.querySelector('.error-registro-trabajador'), exc.message); }
        finally { botonCorregir.disabled = false; guardarNormal.disabled = false; }
    });
    dialogo.addEventListener('close', () => { if (origen) (origen.matches('button') ? origen : origen.querySelector('.abrir-registro-trabajador')).focus(); });
    registro.addEventListener('submit', async evento => {
        evento.preventDefault();
        const boton = registro.querySelector('[type=submit]'); boton.disabled = true;
        try { await guardar(registro, registro.action); }
        catch (exc) { mostrarError(registro.querySelector('.error-registro-trabajador'), exc.message); }
        finally { boton.disabled = false; }
    });
})();
