(() => {
  const bus = document.querySelector('[data-bus-dialog]');
  if (!bus) return;
  document.querySelectorAll('.app-alert').forEach(alert => bus.querySelector('[data-bus-avisos]').append(alert));
  bus.showModal();
  const distribution=document.getElementById('bus-distribution-dialog');
  document.querySelector('[data-distribution-open]')?.addEventListener('click',()=>distribution.showModal());
  document.querySelectorAll('[data-close-dialog]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  document.querySelectorAll('[data-open-seat]').forEach(button => button.addEventListener('click', () => document.getElementById(button.dataset.openSeat).showModal()));
  const free = document.querySelector('[data-free-seat]');
  document.querySelectorAll('[data-empty-seat]').forEach(button => button.addEventListener('click', () => { free.querySelector('[data-free-title]').textContent=`Asiento ${button.dataset.emptySeat} · piso ${button.dataset.floor}`;free.showModal(); }));
  const form=document.querySelector('[data-pasajeros-upload]'),input=form.querySelector('[data-pasajeros-file]'),button=form.querySelector('[data-pasajeros-select]');
  button.addEventListener('click',()=>{if(button.dataset.needsDistribution){distribution.showModal();return;}input.click();});
  input.addEventListener('change',()=>{if(input.files.length)form.requestSubmit();});
  form.addEventListener('submit',()=>{button.disabled=true;button.textContent='Cargando pasajeros…';});
})();
