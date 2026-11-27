const competitionSelect = document.querySelector('[data-tally-competition-select]');
if (competitionSelect) {
    const overview = document.querySelector('[data-tally-overview]');
    const competitionPanels = document.querySelectorAll('[data-tally-competition-panel]');

    function showSelectedTally() {
        const selected = competitionSelect.value;
        overview.hidden = Boolean(selected);
        competitionPanels.forEach((panel) => {
            panel.hidden = panel.id !== selected;
        });
    }

    competitionSelect.addEventListener('change', showSelectedTally);
    window.addEventListener('pageshow', showSelectedTally);
    showSelectedTally();
    competitionSelect.closest('label').hidden = false;
}
