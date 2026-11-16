(function () {
    const hub = document.querySelector('.sports-hub');
    const search = hub.querySelector('#sh-search');
    if (!search) return;
    const cards = Array.from(hub.querySelectorAll('.sh-competition'));
    const buttons = hub.querySelectorAll('[data-filter]');
    const searchable = new Map(cards.map(card => [card, card.textContent.toLocaleLowerCase()]));
    let selected = 'all';
    function filter() {
        const query = search.value.trim().toLocaleLowerCase();
        let visible = 0;
        cards.forEach(card => {
            const matches = (selected === 'all' || card.dataset.competitionStatus === selected) && searchable.get(card).includes(query);
            card.hidden = !matches;
            if (matches) visible++;
            const events = card.querySelector('details');
            if (events && query) { events.open = matches; events.dataset.searchOpened = 'true'; }
            else if (events && events.dataset.searchOpened) { events.open = false; delete events.dataset.searchOpened; }
        });
        hub.querySelector('#sh-no-matches').hidden = visible !== 0;
        hub.querySelector('#sh-filter-count').textContent = visible + ' competition' + (visible === 1 ? '' : 's');
    }
    search.addEventListener('input', filter);
    buttons.forEach(button => button.addEventListener('click', function () {
        selected = button.dataset.filter;
        buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
        filter();
    }));
    hub.querySelector('#sh-reset').addEventListener('click', function () {
        search.value = ''; selected = 'all';
        buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === 'all')));
        filter(); search.focus();
    });
})();
