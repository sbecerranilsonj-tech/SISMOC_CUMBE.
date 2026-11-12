(() => {
 const dialog = document.getElementById('reglas-personal-popup');
 if (!dialog || dialog.dataset.ready) return;
 dialog.dataset.ready = 'true';
 document.querySelectorAll('[data-rule-popup]').forEach(link => link.addEventListener('click', event => {
  event.preventDefault();
  const title = link.dataset.rulePopup;
  dialog.querySelector('h2').textContent = title;
  const frame = dialog.querySelector('iframe');
  frame.title = title;
  frame.src = link.href;
  dialog.showModal();
 }));
 dialog.querySelector('iframe').addEventListener('load', () => {
  const doc = dialog.querySelector('iframe').contentDocument;
  if (!doc || !doc.querySelector('.schedule-page')) return;
  doc.querySelectorAll('.schedule-back,.schedule-brand').forEach(el => el.hidden = true);
 });
 dialog.querySelector('[data-close-rules]').addEventListener('click', () => dialog.close());
 dialog.addEventListener('close', () => { dialog.querySelector('iframe').src = 'about:blank'; });
})();
