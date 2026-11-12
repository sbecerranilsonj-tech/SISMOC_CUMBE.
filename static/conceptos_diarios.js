(() => {
  const form = document.getElementById('conceptos-diarios');
  if (!form) return;
  const table = document.querySelector('.tabla-control-excel');
  const edit = document.getElementById('editar-conceptos');
  if (!edit) return;
  const setEditing = active => {
    table.querySelectorAll('[data-concepto-lectura]').forEach(el => el.hidden = active);
    table.querySelectorAll('.concepto-tiempo').forEach(el => {
      el.hidden = !active;
      el.disabled = !active;
      if (!active) el.value = el.defaultValue;
    });
    form.hidden = !active;
    document.getElementById('editar-tiempos').value = active ? 'si' : 'no';
    edit.setAttribute('aria-expanded', String(active));
    if (active) table.querySelector('.concepto-tiempo').focus();
  };
  edit.addEventListener('click', () => setEditing(edit.getAttribute('aria-expanded') !== 'true'));
  form.querySelector('[data-cancelar-conceptos]').addEventListener('click', () => setEditing(false));
  document.getElementById('correcciones-diarias').addEventListener('submit', () => {
    const active = edit.getAttribute('aria-expanded') === 'true';
    document.getElementById('editar-tiempos').value = active ? 'si' : 'no';
  });
  const restore = document.getElementById('restaurar-conceptos');
  restore?.addEventListener('click', event => {
    if (!confirm('¿Restaurar los cálculos del día y retirar el adicional de feriado o descanso? Las marcaciones y la fecha de feriado se conservan.')) event.preventDefault();
  });
})();
