(() => {
  const dialog = document.querySelector('[data-revision-itinerario]');
  if (!dialog) return;
  document.querySelectorAll('.app-alert').forEach(aviso => dialog.querySelector('[data-revision-avisos]').append(aviso));
  const open = () => { if (!dialog.open) dialog.showModal(); };
  document.querySelector('[data-revision-abrir]')?.addEventListener('click', open);
  dialog.querySelector('[data-revision-cerrar]')?.addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) { const r=dialog.getBoundingClientRect(); if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom) dialog.close(); } });
  open();
})();
