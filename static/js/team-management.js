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

const sportsField = document.querySelector('[data-team-sports]');
const teamCategory = sportsField?.form.querySelector('[name="category"]');
function updateSportsField() {
    sportsField.hidden = teamCategory.value === 'CULTURAL';
}
if (sportsField) {
    updateSportsField();
    teamCategory.addEventListener('change', updateSportsField);
}

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
    const sportHelp = section.querySelector('[data-roster-sport-help]');

    function updateCounts() {
        const active = rosters.get(picker.value)?.element;
        const selected = active?.querySelectorAll('input[type="checkbox"]:checked').length ?? 0;
        rosterPanel.querySelector('[data-roster-active-count]').textContent = `${selected} selected`;
        const players = new Set(Array.from(fields.querySelectorAll('input[type="checkbox"]:checked'), input => input.value));
        const summary = section.querySelector('[data-roster-summary]');
        if (summary) summary.textContent = players.size === 1 ? '1 player selected' : `${players.size} players selected`;
    }

    function filterPlayers() {
        const query = search.value.trim().toLowerCase();
        const labels = rosters.get(picker.value)?.labels ?? [];
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
    function updateAvailableEvents() {
        const selectedSports = new Set(Array.from(sportsField.querySelectorAll('input:checked'), input => input.value));
        const previous = picker.value;
        let firstAvailable = '';
        for (const group of picker.querySelectorAll('optgroup')) {
            for (const option of group.children) {
                option.disabled = !selectedSports.has(option.dataset.sport);
                option.hidden = option.disabled;
                if (!firstAvailable && !option.disabled) firstAvailable = option.value;
            }
            group.hidden = Array.from(group.children).every(option => option.disabled);
        }
        picker.value = Array.from(picker.options).some(option => option.value === previous && !option.disabled)
            ? previous : firstAvailable;
        section.hidden = sportsField.hidden && !section.hasAttribute('data-roster-errors');
        trigger.hidden = sportsField.hidden || !firstAvailable;
        sportHelp.hidden = !trigger.hidden;
        selectEvent();
    }
    if (sportsField) {
        updateAvailableEvents();
        sportsField.addEventListener('change', updateAvailableEvents);
        teamCategory.addEventListener('change', updateAvailableEvents);
    } else {
        trigger.hidden = false;
        selectEvent();
    }
    picker.addEventListener('change', selectEvent);
    search.addEventListener('input', filterPlayers);
    search.addEventListener('keydown', event => {
        if (event.key === 'Enter') event.preventDefault();
    });
    fields.addEventListener('change', updateCounts);
    trigger.addEventListener('click', () => rosterPanel.showModal());
    const assignmentForm = rosterPanel.closest('[data-workspace-assignments]');
    if (assignmentForm) {
        let submitted = false;
        assignmentForm.addEventListener('submit', () => { submitted = true; });
        rosterPanel.addEventListener('close', () => {
            if (!submitted) {
                assignmentForm.reset();
                selectEvent();
            }
        });
    }
    rosterPanel.querySelectorAll('[data-roster-close]').forEach(button => {
        button.addEventListener('click', () => rosterPanel.close());
    });
    rosterPanel.addEventListener('close', () => trigger.focus());
    if (!trigger.hidden && (location.hash === '#event-roster' || section.hasAttribute('data-roster-errors'))) {
        rosterPanel.showModal();
    } else if (error) {
        section.prepend(error);
    }
}

document.querySelectorAll('[data-workspace-tabs]').forEach(tabList => {
    const tabs = Array.from(tabList.querySelectorAll('[data-tab-target]'));
    const panels = tabs.map(tab => document.getElementById(tab.dataset.tabTarget)).filter(Boolean);

    function activate(targetId, updateHash = false) {
        tabs.forEach(tab => {
            const active = tab.dataset.tabTarget === targetId;
            tab.classList.toggle('is-active', active);
            tab.setAttribute('aria-selected', active ? 'true' : 'false');
            tab.tabIndex = active ? 0 : -1;
        });
        panels.forEach(panel => {
            panel.hidden = panel.id !== targetId;
        });
        if (updateHash && history.replaceState) {
            history.replaceState(null, '', `#${targetId}`);
        }
    }

    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => activate(tab.dataset.tabTarget, true));
        tab.addEventListener('keydown', event => {
            if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
            event.preventDefault();
            const next = tabs[(index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
            next.focus();
            activate(next.dataset.tabTarget, true);
        });
    });

    const hashId = location.hash.replace(/^#/, '');
    const initial = tabs.some(tab => tab.dataset.tabTarget === hashId) ? hashId : tabs[0]?.dataset.tabTarget;
    if (initial) activate(initial, false);
});
