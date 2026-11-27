(() => {
  const panel = document.getElementById('movil-accesos');
  if (!panel) return;
  const dialog = panel.querySelector('[data-activated-dialog]');
  const activatedBody = panel.querySelector('[data-activated-body]');
  function filterPending() {
    let pending = 0;
    for (const row of panel.querySelectorAll('tr[data-perfil]')) {
      const isPending = row.querySelector('[data-access-status]')?.textContent.trim() === 'Pendiente';
      row.hidden = !isPending;
      if (isPending) pending++;
    }
    const empty = panel.querySelector('[data-pending-empty]');
    if (empty) empty.hidden = pending !== 0;
  }
  filterPending();
  function renderActivated() {
    activatedBody.replaceChildren();
    let count = 0;
    for (const row of panel.querySelectorAll('tr[data-perfil]')) {
      if (row.querySelector('[data-access-status]')?.textContent.trim() !== 'Activado') continue;
      const copy = document.createElement('tr');
      for (const indice of [0, 1, 2, 3, 6]) {
        const cell = row.cells[indice];
        if (!cell) continue;
        const td = document.createElement('td');
        td.textContent = cell.textContent.trim();
        copy.append(td);
      }
      activatedBody.append(copy);
      count++;
    }
    panel.querySelector('[data-activated-count]').textContent = `${count} cuenta${count === 1 ? '' : 's'} activada${count === 1 ? '' : 's'}`;
    if (!count) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 5;
      cell.textContent = 'No hay cuentas activadas en este listado.';
      row.append(cell); activatedBody.append(row);
    }
  }
  panel.querySelector('[data-open-activated]')?.addEventListener('click', () => {
    renderActivated();
    dialog.showModal();
    refresh();
  });
  panel.querySelector('[data-close-activated]')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right ||
        event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  panel.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-copy-activation]');
    if (!button) return;
    const code = button.closest('td').querySelector('[data-activation-code]');
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code.textContent.trim());
      button.textContent = 'Copiado';
    } catch (_) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges(); selection.addRange(range);
      button.textContent = 'Seleccionado: use Ctrl + C';
    }
  });
  let loading = false;
  async function refresh() {
    if (document.hidden || loading) return;
    loading = true;
    try {
      const response = await fetch(panel.dataset.estadosUrl, {cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok || response.redirected) return;
      const data = await response.json();
      for (const perfil of data.perfiles) {
        const row = panel.querySelector(`[data-perfil="${Number(perfil.id)}"]`);
        if (!row) continue;
        row.querySelector('[data-access-status]').textContent = perfil.estado;
        if (perfil.estado !== 'Pendiente') {
          const cell = row.querySelector('[data-activacion-cell]');
          cell.textContent = perfil.estado === 'Activado' ? 'Código utilizado' : perfil.estado;
        }
      }
      filterPending();
      if (dialog?.open) renderActivated();
    } catch (_) {
      // Conserva el estado mostrado si no hay conexión; reintenta en la próxima consulta.
    } finally { loading = false; }
  }
  setInterval(refresh, 5000);
  document.addEventListener('visibilitychange', refresh);
})();
