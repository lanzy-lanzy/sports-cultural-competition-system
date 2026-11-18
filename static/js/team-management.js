document.querySelectorAll('[data-select-all]').forEach(toggle => {
    const id = toggle.dataset.selectAll;
    const form = document.getElementById(id);
    const boxes = Array.from(document.querySelectorAll('input[name="selected"]')).filter(box => box.form === form);
    const counter = document.querySelector(`[data-selection-count="${id}"]`);
    const submit = form.querySelector('[data-bulk-submit]');
    function update() {
        const count = boxes.filter(box => box.checked).length;
        toggle.checked = boxes.length > 0 && count === boxes.length;
        toggle.indeterminate = count > 0 && count < boxes.length;
        counter.textContent = `${count} selected`;
        submit.disabled = count === 0;
    }
    toggle.addEventListener('change', () => { boxes.forEach(box => { box.checked = toggle.checked; }); update(); });
    boxes.forEach(box => box.addEventListener('change', update));
    update();
});

document.querySelectorAll('[data-event-roster]').forEach(roster => {
    const counter = roster.querySelector('[data-roster-count]');
    roster.addEventListener('change', () => {
        const count = roster.querySelectorAll('input[type="checkbox"]:checked').length;
        counter.textContent = `${count} selected`;
    });
});
