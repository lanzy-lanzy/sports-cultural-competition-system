document.querySelectorAll('[data-tally-filter-tabs]').forEach((row) => {
    const selected = row.querySelector('[aria-current="true"]');
    if (!selected) return;

    const overflow = selected.getBoundingClientRect().right - row.getBoundingClientRect().right;
    if (overflow > 0) row.scrollLeft += Math.ceil(overflow);
});

document.querySelectorAll('[data-tally-tabs]').forEach((tabList) => {
    const tabs = Array.from(tabList.querySelectorAll('button[aria-controls]'));
    if (tabs.length < 2) return;

    const panels = tabs.map((tab) => document.getElementById(tab.getAttribute('aria-controls')));
    if (panels.some((panel) => !panel)) return;

    function activateTab(activeIndex) {
        tabs.forEach((tab, index) => {
            const active = index === activeIndex;
            tab.setAttribute('aria-selected', String(active));
            tab.tabIndex = active ? 0 : -1;
            panels[index].hidden = !active;
        });
    }

    tabList.setAttribute('role', 'tablist');
    tabs.forEach((tab, index) => {
        tab.setAttribute('role', 'tab');
        panels[index].setAttribute('role', 'tabpanel');
        panels[index].setAttribute('aria-labelledby', tab.id);
        panels[index].tabIndex = 0;

        tab.addEventListener('click', () => activateTab(index));
        tab.addEventListener('keydown', (event) => {
            let nextIndex;
            switch (event.key) {
                case 'ArrowLeft':
                    nextIndex = (index + tabs.length - 1) % tabs.length;
                    break;
                case 'ArrowRight':
                    nextIndex = (index + 1) % tabs.length;
                    break;
                case 'Home':
                    nextIndex = 0;
                    break;
                case 'End':
                    nextIndex = tabs.length - 1;
                    break;
                default:
                    return;
            }
            event.preventDefault();
            activateTab(nextIndex);
            tabs[nextIndex].focus();
        });
    });
    activateTab(0);
    tabList.hidden = false;
});
