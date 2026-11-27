/* Movimiento inspirado en la secuencia Glassy Dashboard V5. Sin dependencias. */
(() => {
  'use strict';
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (!Element.prototype.animate || preference.matches) return;
  const ownAnimations = new Set();
  const running = new WeakMap();
  const selector = '.content-panel, .kpi-box, .accounting-tile, .modulo-dashboard';
  const visible = element => {
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.top < innerHeight && rect.bottom > 0;
  };
  function enter(element, delay = 0, dialog = false) {
    if (preference.matches || !visible(element)) return;
    running.get(element)?.cancel();
    const animation = element.animate([
      {opacity: 0, transform: dialog ? 'translateY(14px) scale(.98)' : 'translateY(18px)', filter: 'blur(3px)'},
      {opacity: 1, transform: 'translateY(0) scale(1)', filter: 'blur(0)'}
    ], {duration: dialog ? 320 : 460, delay, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'backwards'});
    running.set(element, animation);
    ownAnimations.add(animation);
    const clear = () => {
      ownAnimations.delete(animation);
      if (running.get(element) === animation) running.delete(element);
    };
    animation.addEventListener('finish', clear, {once: true});
    animation.addEventListener('cancel', clear, {once: true});
  }
  function showView(view) {
    if (!view.classList.contains('active') || preference.matches) return;
    const candidates = [...view.querySelectorAll(selector)].filter(visible);
    // Un solo movimiento por superficie: no acumular transformaciones anidadas.
    const selected = candidates.filter(element => !candidates.some(parent => parent !== element && parent.contains(element)));
    selected.slice(0, 12).forEach((element, index) => enter(element, Math.min(index * 65, 325)));
  }
  function cancelView(view) {
    view.querySelectorAll(selector).forEach(element => running.get(element)?.cancel());
  }
  function watchDialog(dialog) {
    new MutationObserver(() => {
      if (dialog.open) enter(dialog, 0, true);
      else running.get(dialog)?.cancel();
    }).observe(dialog, {attributes: true, attributeFilter: ['open']});
    if (dialog.open) enter(dialog, 0, true);
  }
  function init() {
    document.documentElement.classList.add('sismoc-motion-ready');
    document.querySelectorAll('.view-section').forEach(view => {
      let active = view.classList.contains('active');
      new MutationObserver(() => {
        const next = view.classList.contains('active');
        if (next !== active) {
          active = next;
          if (active) showView(view); else cancelView(view);
        }
      }).observe(view, {attributes: true, attributeFilter: ['class']});
      if (active) showView(view);
    });
    document.querySelectorAll('dialog').forEach(watchDialog);
    preference.addEventListener('change', event => {
      if (event.matches) [...ownAnimations].forEach(animation => animation.cancel());
    });
    // Evitar repetir la entrada cuando Windows restaura una ventana o pestaña.
    window.addEventListener('pagehide', () => [...ownAnimations].forEach(animation => animation.cancel()));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
