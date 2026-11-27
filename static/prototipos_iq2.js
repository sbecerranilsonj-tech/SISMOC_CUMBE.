/* Simulaciones del IQ2. Sin solicitudes de red, GPS ni persistencia. */
(() => {
    'use strict';
    const byId = (id) => document.getElementById(id);
    const money = (cents) => new Intl.NumberFormat('es-PE', {style: 'currency', currency: 'PEN'}).format(cents / 100);
    const notify = (message, error = false) => {
        const box = byId('feedback');
        box.textContent = message;
        box.classList.toggle('error', error);
        box.hidden = false;
    };
    function selectPanel() {
        const requested = location.hash.slice(1) || 'conciliacion';
        const key = ['conciliacion', 'asistencia', 'rutas', 'croquis', 'kanban'].includes(requested) ? requested : 'conciliacion';
        document.querySelectorAll('[data-view]').forEach((view) => { view.hidden = view.dataset.view !== key; });
        document.querySelectorAll('[data-panel]').forEach((link) => {
            const active = link.dataset.panel === key;
            link.classList.toggle('active', active);
            if (active) link.setAttribute('aria-current', 'page');
            else link.removeAttribute('aria-current');
        });
        byId('feedback').hidden = true;
    }
    window.addEventListener('hashchange', selectPanel);
    selectPanel();

    function cell(row, value) {
        const element = document.createElement('td');
        element.textContent = value;
        row.append(element);
        return element;
    }
    function status(row, label, style) {
        const element = cell(row, '');
        const badge = document.createElement('span');
        badge.className = `pill ${style}`;
        badge.textContent = label;
        element.append(badge);
    }
    function emptyRow(body, columns, message) {
        body.replaceChildren();
        const row = document.createElement('tr');
        const td = cell(row, message);
        td.colSpan = columns;
        td.className = 'empty';
        body.append(row);
    }

    // Importes en céntimos para evitar diferencias de punto flotante.
    const bank = [{id: 'DEMO-1001', amount: 12000}, {id: 'DEMO-1002', amount: 8500}, {id: 'DEMO-1003', amount: 20000}, {id: 'DEMO-1004', amount: 6000}];
    const sales = [{id: 'DEMO-1001', amount: 12000, medium: 'Yape'}, {id: 'DEMO-1002', amount: 8500, medium: 'Plin'}, {id: 'DEMO-1003', amount: 18000, medium: 'POS'}, {id: 'DEMO-1005', amount: 9500, medium: 'Yape'}];
    let sampleLoaded = false;
    let report = [];
    byId('load-sample').addEventListener('click', () => {
        sampleLoaded = true;
        report = [];
        byId('bank-source').textContent = `${bank.length} movimientos ficticios listos`;
        byId('sales-source').textContent = `${sales.length} ventas ficticias listas`;
        byId('bank-total').textContent = money(bank.reduce((sum, item) => sum + item.amount, 0));
        byId('match-count').textContent = '—';
        byId('issue-count').textContent = '—';
        byId('reconcile').disabled = false;
        byId('export-report').disabled = true;
        emptyRow(byId('reconciliation-rows'), 6, 'Muestra cargada. Pulsa Simular conciliación.');
        notify('Se cargaron datos ficticios de banco y ventas. No se han leído archivos de la empresa.');
    });
    byId('reconcile').addEventListener('click', () => {
        if (!sampleLoaded) return;
        const ids = [...new Set([...bank, ...sales].map((item) => item.id))];
        report = ids.map((id) => {
            const b = bank.find((item) => item.id === id);
            const s = sales.find((item) => item.id === id);
            const label = !b ? 'Sin movimiento bancario' : !s ? 'Sin venta asociada' : b.amount === s.amount ? 'Coincide' : 'Diferencia de importe';
            return {id, medium: s?.medium || '—', bank: b?.amount ?? null, sales: s?.amount ?? null, difference: (b?.amount || 0) - (s?.amount || 0), label};
        });
        const body = byId('reconciliation-rows');
        body.replaceChildren();
        report.forEach((item) => {
            const row = document.createElement('tr');
            [item.id, item.medium, item.bank === null ? '—' : money(item.bank), item.sales === null ? '—' : money(item.sales), money(item.difference)].forEach((value) => cell(row, value));
            status(row, item.label, item.label === 'Coincide' ? 'green' : 'amber');
            body.append(row);
        });
        const matches = report.filter((item) => item.label === 'Coincide').length;
        byId('match-count').textContent = matches;
        byId('issue-count').textContent = report.length - matches;
        byId('export-report').disabled = false;
        notify(`Cruce de ejemplo: ${matches} coincidencias y ${report.length - matches} operaciones por revisar.`);
    });
    byId('export-report').addEventListener('click', () => {
        if (!report.length) return;
        const csvCell = (value) => `"${String(value).replaceAll('"', '""')}"`;
        const rows = [['REPORTE DE DEMOSTRACIÓN - DATOS FICTICIOS'], ['Operación', 'Medio', 'Banco PEN', 'Ventas PEN', 'Diferencia PEN', 'Estado'], ...report.map((item) => [item.id, item.medium, item.bank === null ? '' : (item.bank / 100).toFixed(2), item.sales === null ? '' : (item.sales / 100).toFixed(2), (item.difference / 100).toFixed(2), item.label])];
        const url = URL.createObjectURL(new Blob(['\ufeff' + rows.map((row) => row.map(csvCell).join(';')).join('\r\n')], {type: 'text/csv;charset=utf-8'}));
        const link = document.createElement('a');
        link.href = url;
        link.download = 'conciliacion_DEMOSTRACION.csv';
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    });

    const eventOrder = ['Entrada', 'Salida a refrigerio', 'Retorno', 'Salida'];
    let marks = [];
    function updateClock() {
        const now = new Date();
        byId('demo-clock').textContent = now.toLocaleTimeString('es-PE', {hour12: false});
        byId('demo-date').textContent = now.toLocaleDateString('es-PE', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'});
    }
    updateClock();
    setInterval(updateClock, 1000);
    document.querySelectorAll('[data-mark]').forEach((button) => button.addEventListener('click', () => {
        const expected = eventOrder[marks.length];
        if (!expected) return notify('La jornada de ejemplo está completa. Reinicia la demostración para volver a marcar.', true);
        if (button.dataset.mark !== expected) return notify(`En esta demostración corresponde registrar: ${expected}.`, true);
        marks.push({type: expected, time: new Date().toLocaleTimeString('es-PE', {hour12: false})});
        const list = byId('mobile-marks');
        list.replaceChildren();
        marks.forEach((mark) => {
            const li = document.createElement('li');
            const name = document.createElement('span');
            const time = document.createElement('strong');
            name.textContent = mark.type;
            time.textContent = mark.time;
            li.append(name, time);
            list.append(li);
        });
        notify(`${expected}: marca simulada. No se envió al servidor ni se capturó GPS.`);
    }));
    byId('reset-marks').addEventListener('click', () => {
        marks = [];
        const li = document.createElement('li');
        li.className = 'muted';
        li.textContent = 'Todavía no hay marcaciones simuladas.';
        byId('mobile-marks').replaceChildren(li);
        notify('Se reinició la jornada de demostración.');
    });

    // Los descansos son supuestos de la muestra; no se deducen de registros reales.
    const trips = [];
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    byId('trip-date').value = today;
    byId('trip-form').addEventListener('submit', (event) => {
        event.preventDefault();
        if (!event.currentTarget.reportValidity()) return;
        const driver = byId('trip-driver').value;
        const rest = driver === 'A' ? 10 : 5;
        const minimum = Number(byId('rest-limit').value);
        if (rest < minimum) return notify(`Asignación simulada bloqueada: descanso supuesto de ${rest} h, inferior al umbral elegido de ${minimum} h.`, true);
        const trip = {date: byId('trip-date').value, time: byId('trip-time').value, route: byId('trip-route').value, bus: byId('trip-bus').value, driver};
        if (trips.some((t) => t.date === trip.date && t.time === trip.time && (t.bus === trip.bus || t.driver === trip.driver))) {
            return notify('La muestra ya contiene una salida a la misma fecha y hora para esta unidad o conductor.', true);
        }
        trips.push(trip);
        const body = byId('trip-rows');
        body.replaceChildren();
        trips.forEach((item) => {
            const row = document.createElement('tr');
            [`${item.date} ${item.time}`, item.route, item.bus, `Ejemplo ${item.driver}`].forEach((value) => cell(row, value));
            status(row, 'Asignación simulada', 'green');
            body.append(row);
        });
        notify('Servicio agregado a la muestra. La comprobación de intervalos, relevos y reglas reales está pendiente.');
    });
    byId('reset-trips').addEventListener('click', () => {
        trips.length = 0;
        emptyRow(byId('trip-rows'), 5, 'Todavía no hay servicios en esta demostración.');
        notify('Se eliminaron los servicios de ejemplo de esta visita.');
    });

    let floor = 1;
    let selectedSeat = null;
    let occupiedSeats = new Set([3, 4, 9, 15, 16, 25, 30]);
    function drawSeats() {
        const single = byId('bus-layout').value === 'single';
        const capacity = single ? 40 : 44;
        const start = single || floor === 1 ? 1 : 13;
        const end = single ? 40 : floor === 1 ? 12 : 44;
        byId('floor-controls').hidden = single;
        document.querySelectorAll('[data-floor]').forEach((button) => button.setAttribute('aria-pressed', String(Number(button.dataset.floor) === floor)));
        const grid = byId('seat-grid');
        grid.replaceChildren();
        for (let number = start; number <= end; number++) {
            const seat = document.createElement('button');
            seat.type = 'button';
            seat.className = 'seat';
            seat.textContent = String(number).padStart(2, '0');
            seat.disabled = occupiedSeats.has(number);
            seat.classList.toggle('chosen', number === selectedSeat);
            seat.setAttribute('aria-label', `Asiento ${number}, ${seat.disabled ? 'ocupado en la muestra' : 'libre'}`);
            seat.setAttribute('aria-pressed', String(number === selectedSeat));
            seat.addEventListener('click', () => {selectedSeat = number; drawSeats();});
            grid.append(seat);
        }
        const occupied = [...occupiedSeats].filter((seat) => seat <= capacity).length;
        byId('occupancy').textContent = `${occupied} de ${capacity} asientos`;
        byId('selected-seat').textContent = selectedSeat ? `Asiento ${String(selectedSeat).padStart(2, '0')}` : 'Elige un asiento';
        byId('seat-detail').textContent = selectedSeat ? `${single ? 'Un piso' : `Piso ${floor}`} · Selección de demostración` : 'Selecciona un asiento libre del croquis.';
        byId('occupy-seat').disabled = selectedSeat === null;
    }
    document.querySelectorAll('[data-floor]').forEach((button) => button.addEventListener('click', () => {
        floor = Number(button.dataset.floor);
        selectedSeat = null;
        drawSeats();
    }));
    byId('bus-layout').addEventListener('change', () => {floor = 1; selectedSeat = null; drawSeats();});
    byId('occupy-seat').addEventListener('click', () => {
        if (selectedSeat === null) return;
        const number = selectedSeat;
        occupiedSeats.add(number);
        selectedSeat = null;
        drawSeats();
        notify(`Asiento ${number} ocupado solo en la muestra. No se emitió un boleto.`);
    });
    byId('reset-seats').addEventListener('click', () => {
        occupiedSeats = new Set([3, 4, 9, 15, 16, 25, 30]);
        selectedSeat = null;
        drawSeats();
        notify('Croquis de ejemplo restablecido.');
    });
    drawSeats();
})();
