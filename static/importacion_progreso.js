(() => {
    'use strict';
    const host = document.getElementById('resultadoExcelBox');
    const template = document.getElementById('plantilla-progreso-importacion');
    if (!host || !template) return;
    let activa = false;
    window.procesarExcel = async file => {
        if (!file || activa) return;
        activa = true;
        const controls = [...document.querySelectorAll('.zk-upload-trigger, #excelInput')];
        controls.forEach(control => control.disabled = true);
        host.replaceChildren(template.content.cloneNode(true));
        host.style.display = 'block';
        const panel = host.querySelector('.zk-import-progress');
        const bar = host.querySelector('[data-import-bar]');
        const track = host.querySelector('[role=progressbar]');
        const status = host.querySelector('[data-import-status]');
        const percent = host.querySelector('[data-import-percent]');
        const count = host.querySelector('[data-import-count]');
        const result = host.querySelector('[data-import-result]');
        const stages = [...host.querySelectorAll('[data-import-stage]')];
        host.querySelector('[data-import-file]').textContent = `${file.name} · ${(file.size / 1024).toLocaleString('es-PE', {maximumFractionDigits: 0})} KB`;
        let completo = false;
        let ultimo = 0;
        function avanzar(evento) {
            if (evento.tipo === 'espera') return;
            if (evento.tipo === 'error') throw new Error(evento.detail);
            if (evento.tipo === 'completado') {
                completo = true;
                panel.classList.remove('is-indeterminate');
                panel.classList.add('is-complete');
                panel.setAttribute('aria-busy', 'false');
                bar.style.width = '100%';
                track.setAttribute('aria-valuenow', '100');
                percent.textContent = '100 %';
                host.querySelector('#titulo-importacion').textContent = 'Asistencia importada';
                status.textContent = 'Archivo guardado. Ya puedes revisar sus marcaciones.';
                stages.forEach(s => { s.dataset.state = 'done'; s.removeAttribute('aria-current'); });
                result.hidden = false;
                const data = evento.resultado;
                const resumen = document.createElement('p');
                resumen.textContent = `${data.marcaciones_nuevas} marcas nuevas · ${data.marcaciones_repetidas} ya registradas · ${data.codigos_biometricos} códigos`;
                result.appendChild(resumen);
                const link = document.createElement('a');
                link.className = 'btn-cumbe';
                link.href = '?vista=excel-zk&grupo_carga=' + encodeURIComponent(data.carga_id);
                link.textContent = 'Ver importación';
                result.appendChild(link);
                if (data.alertas?.length) {
                    const notes = document.createElement('details');
                    notes.className = 'zk-import-notes';
                    const heading = document.createElement('summary');
                    heading.textContent = `Notas de importación (${data.alertas.length})`;
                    notes.appendChild(heading);
                    const list = document.createElement('ul');
                    data.alertas.forEach(text => { const item = document.createElement('li'); item.textContent = text; list.appendChild(item); });
                    notes.appendChild(list);
                    result.appendChild(notes);
                }
                return;
            }
            if (evento.tipo !== 'progreso') return;
            ultimo = Math.max(ultimo, Math.min(99, Number(evento.porcentaje) || 0));
            panel.classList.toggle('is-indeterminate', evento.etapa === 'validando');
            percent.textContent = evento.etapa === 'validando' ? 'Validando' : `${ultimo} %`;
            if (evento.etapa === 'validando') track.removeAttribute('aria-valuenow');
            else track.setAttribute('aria-valuenow', String(ultimo));
            bar.style.width = `${ultimo}%`;
            status.textContent = {validando: 'Leyendo el Excel y comprobando los datos…', registrando: 'Registrando marcaciones y comprobando repeticiones…', guardando: 'Guardando los resultados de la importación…'}[evento.etapa] || 'Procesando archivo…';
            if (evento.total) count.textContent = `${Number(evento.actual).toLocaleString('es-PE')} de ${Number(evento.total).toLocaleString('es-PE')} filas`;
            const actual = stages.findIndex(s => s.dataset.importStage === evento.etapa);
            stages.forEach((s, i) => {
                s.dataset.state = i < actual ? 'done' : i === actual ? 'active' : 'waiting';
                if (i === actual) s.setAttribute('aria-current', 'step');
                else s.removeAttribute('aria-current');
            });
        }
        try {
            const data = new FormData();
            data.append('file', file);
            data.append('progreso', 'si');
            const response = await fetch(host.dataset.importUrl, {method: 'POST', headers: {'X-CSRFToken': host.dataset.csrf}, body: data});
            if (!response.ok || !response.headers.get('content-type')?.includes('application/x-ndjson')) {
                const error = await response.json().catch(() => null);
                throw new Error(error?.detail || 'No se pudo iniciar la importación. Revisa tu sesión y el archivo.');
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let pending = '';
            while (true) {
                const {value, done} = await reader.read();
                pending += decoder.decode(value, {stream: !done});
                const lines = pending.split('\n');
                pending = lines.pop();
                for (const line of lines) if (line.trim()) avanzar(JSON.parse(line));
                if (done) break;
            }
            if (pending.trim()) avanzar(JSON.parse(pending));
            if (!completo) throw new Error('Se interrumpió la conexión. Revisa los archivos cargados antes de volver a subirlo.');
        } catch (error) {
            panel.classList.remove('is-indeterminate');
            panel.classList.add('is-error');
            panel.setAttribute('aria-busy', 'false');
            host.querySelector('#titulo-importacion').textContent = 'Revisa la importación';
            percent.textContent = 'Atención';
            status.textContent = error.message || 'No se pudo confirmar la importación. Revisa los archivos cargados antes de reintentar.';
            status.setAttribute('role', 'alert');
        } finally {
            activa = false;
            controls.forEach(control => control.disabled = false);
            const input = document.getElementById('excelInput');
            if (input) input.value = '';
        }
    };
})();
