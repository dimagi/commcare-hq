import 'commcarehq';
import 'hqwebapp/js/htmx_base';

import 'hqwebapp/js/htmx_utils/hq_hx_loading';
import 'hqwebapp/js/htmx_utils/hq_hx_refresh';
import 'prototype/js/data_cleaning/hq_hx_select_all';

import { Tooltip, Alert } from 'bootstrap5';
import Sortable from 'sortablejs';
import _ from 'underscore';
import Alpine from 'alpinejs';

import htmx from 'htmx.org';

Alpine.store('whitespaces', {
    show: false,
});
Alpine.start();

htmx.config.timeout = 20000;

htmx.onLoad((content) => {
    _.each(content.querySelectorAll(".sortable"), (sortable) => {
        let sortableInstance = new Sortable(sortable, {
            animation: 150,

            // Make the `.htmx-indicator` unsortable
            filter: ".htmx-indicator",
            onMove: (evt) => {
                return evt.related.className.indexOf('htmx-indicator') === -1;
            },

            // Disable sorting on the `end` event
            onEnd: (evt) => {
                // todo fix or figure out if we still need this library
                // evt.target.option("disabled", true);
            },
        });

        // Re-enable sorting on the `htmx:afterSwap` event
        sortable.addEventListener("htmx:afterSwap", () => {
            sortableInstance.option("disabled", false);
        });
    });

    _.each(document.querySelectorAll('[data-bs-toggle="tooltip"]'), (el) => {
        new Tooltip(el);
    });
});

document.body.addEventListener('htmx:afterRequest', (evt) => {
    if (evt.detail.elt.classList.contains('htmx-request')) {
        evt.detail.elt.classList.remove('htmx-request');
    }
});

const cleanDataOffcanvas = document.getElementById('editOffcanvas');
cleanDataOffcanvas.addEventListener('hidden.bs.offcanvas', () => {
    if (document.getElementById('numChangesDCAlert')) {
        const numChangesDCAlert = Alert.getOrCreateInstance('#numChangesDCAlert');
        numChangesDCAlert.close();
    }
});

global.refreshFilters = (selector) => {
    htmx.trigger(selector, 'refreshFilters');
};
