(() => {
  const panel = document.getElementById('movil-accesos');
  if (!panel) return;
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
    } catch (_) {
      // Conserva el estado mostrado si no hay conexión; reintenta en la próxima consulta.
    } finally { loading = false; }
  }
  setInterval(refresh, 5000);
  document.addEventListener('visibilitychange', refresh);
})();
