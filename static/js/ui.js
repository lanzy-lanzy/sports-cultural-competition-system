/* Minimal, dependency-free UI helpers.
 * Replaces the Flowbite dropdown behaviour previously loaded from a CDN,
 * keeping the same markup contract: a trigger with [data-dropdown-toggle]
 * targets the dropdown element by id. */
(function () {
    'use strict';

    function closeAll(except) {
        document.querySelectorAll('[data-dropdown-toggle]').forEach(function (trigger) {
            var menu = document.getElementById(trigger.getAttribute('data-dropdown-toggle'));
            if (!menu || menu === except) return;
            menu.classList.add('hidden');
            trigger.setAttribute('aria-expanded', 'false');
        });
    }

    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('[data-dropdown-toggle]');
        if (trigger) {
            event.preventDefault();
            var menu = document.getElementById(trigger.getAttribute('data-dropdown-toggle'));
            if (!menu) return;
            var willOpen = menu.classList.contains('hidden');
            closeAll(willOpen ? menu : null);
            menu.classList.toggle('hidden');
            trigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
            return;
        }
        if (!event.target.closest('[id][data-dropdown-toggle], #user-menu, [data-dropdown-toggle]')) {
            closeAll(null);
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') closeAll(null);
    });
})();
