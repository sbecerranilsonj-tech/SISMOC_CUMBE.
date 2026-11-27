(() => {
    const dialogs = document.querySelectorAll('.schedule-dialog');
    let trigger;
    document.querySelectorAll('[data-open-schedule]').forEach(button => {
        button.addEventListener('click', () => {
            const dialog = document.getElementById(button.dataset.openSchedule);
            if (dialog) { trigger = button; dialog.showModal(); }
        });
    });
    dialogs.forEach(dialog => {
        dialog.querySelector('[data-close-schedule]').addEventListener('click', () => dialog.close());
        dialog.addEventListener('click', event => {
            const r = dialog.getBoundingClientRect();
            if (event.target === dialog && (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)) dialog.close();
        });
        dialog.addEventListener('close', () => { if (trigger) trigger.focus({preventScroll:true}); });
    });
    const errores = document.querySelector('.schedule-dialog[data-auto-open]');
    if (errores) errores.showModal();
})();
