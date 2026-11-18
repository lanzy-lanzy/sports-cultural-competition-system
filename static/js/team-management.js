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

const rosterPanel = document.querySelector('#event-roster-panel');
if (typeof rosterPanel?.showModal === 'function') {
    const section = document.querySelector('#event-roster');
    const trigger = section.querySelector('[data-roster-open]');
    const picker = rosterPanel.querySelector('#roster-event-picker');
    const search = rosterPanel.querySelector('#roster-player-search');
    const fields = rosterPanel.querySelector('[data-roster-panel-fields]');
    const noResults = rosterPanel.querySelector('[data-roster-no-results]');
    const rosters = new Map(Array.from(section.querySelectorAll('[data-event-roster]'), roster => [
        roster.dataset.eventRoster,
        { element: roster, labels: Array.from(roster.querySelectorAll('fieldset label')) }
    ]));
    const error = section.querySelector('[data-roster-error]');
    if (error) rosterPanel.querySelector('.event-roster-panel-body').prepend(error);
    for (const roster of rosters.values()) {
        roster.element.open = true;
        fields.append(roster.element);
    }
    section.querySelector('[data-roster-fields]').hidden = true;
    trigger.hidden = false;

    function updateCounts() {
        const active = rosters.get(picker.value).element;
        const selected = active.querySelectorAll('input[type="checkbox"]:checked').length;
        rosterPanel.querySelector('[data-roster-active-count]').textContent = `${selected} selected`;
        const players = new Set(Array.from(fields.querySelectorAll('input[type="checkbox"]:checked'), input => input.value));
        section.querySelector('[data-roster-summary]').textContent =
            players.size === 1 ? '1 player selected' : `${players.size} players selected`;
    }

    function filterPlayers() {
        const query = search.value.trim().toLowerCase();
        const { labels } = rosters.get(picker.value);
        let matches = 0;
        for (const label of labels) {
            label.hidden = !label.textContent.toLowerCase().includes(query);
            if (!label.hidden) matches++;
        }
        noResults.hidden = !query || !labels.length || matches > 0;
    }

    function selectEvent() {
        for (const [id, roster] of rosters) roster.element.hidden = id !== picker.value;
        search.value = '';
        filterPlayers();
        updateCounts();
    }

    const firstError = fields.querySelector('[data-event-errors]');
    if (firstError) picker.value = firstError.dataset.eventRoster;
    selectEvent();
    picker.addEventListener('change', selectEvent);
    search.addEventListener('input', filterPlayers);
    search.addEventListener('keydown', event => {
        if (event.key === 'Enter') event.preventDefault();
    });
    fields.addEventListener('change', updateCounts);
    trigger.addEventListener('click', () => rosterPanel.showModal());
    rosterPanel.querySelectorAll('[data-roster-close]').forEach(button => {
        button.addEventListener('click', () => rosterPanel.close());
    });
    rosterPanel.addEventListener('close', () => trigger.focus());
    if (location.hash === '#event-roster' || section.hasAttribute('data-roster-errors')) rosterPanel.showModal();
}
