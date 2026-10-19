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

/* Submit-button loader.
 * Opt a submit button in with [data-loader]. It needs two children:
 *   [data-loader-idle]  - shown normally
 *   [data-loader-busy]  - shown while the form is in flight (add `hidden`)
 * On submit the two swap, the button disables itself, and aria-busy marks
 * the pending state for assistive tech. A second submit is ignored so the
 * form cannot be posted twice. */
(function () {
    'use strict';

    function setLoading(button, loading) {
        var idle = button.querySelector('[data-loader-idle]');
        var busy = button.querySelector('[data-loader-busy]');
        if (idle) idle.hidden = loading;
        if (busy) busy.hidden = !loading;
        button.disabled = loading;
        button.setAttribute('aria-busy', loading ? 'true' : 'false');
    }

    function reset(form) {
        var button = form.querySelector('[data-loader]');
        if (!button) return;
        button.removeAttribute('data-loader-busy');
        setLoading(button, false);
    }

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!form || form.nodeType !== 1 || form.tagName !== 'FORM') return;

        var button = form.querySelector('[data-loader]');
        if (!button) return;

        /* Already in flight - swallow the second submit rather than letting
         * the browser post the form a second time. */
        if (button.getAttribute('data-loader-busy') === '1') {
            event.preventDefault();
            return;
        }
        button.setAttribute('data-loader-busy', '1');
        setLoading(button, true);
    });

    /* Back/forward navigation can restore a page from the bfcache with the
     * button still disabled. Put it back to its idle state. */
    window.addEventListener('pageshow', function (event) {
        if (!event.persisted) return;
        var form = document.querySelector('form');
        if (form) reset(form);
    });
})();
