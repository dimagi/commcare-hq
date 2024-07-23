'use strict';

hqDefine("prototype/js/data_cleaning",[
    'underscore',
    'sortablejs',
    'es6!hqwebapp/js/bootstrap5_loader',
    'prototype/js/htmx_action',
    'prototype/js/hq_htmx_loading',
    'prototype/js/hq_htmx_select_all',
    'prototype/js/hq_htmx_refresh',
], function (_, Sortable, bootstrap) {
    let htmx = window.htmx;
    htmx.config.timeout = 2000;
    htmx.onLoad(function (content) {

        _.each(content.querySelectorAll(".sortable"), function (sortable) {
            let sortableInstance = new Sortable(sortable, {
                animation: 150,

                // Make the `.htmx-indicator` unsortable
                filter: ".htmx-indicator",
                onMove: function (evt) {
                    return evt.related.className.indexOf('htmx-indicator') === -1;
                },

                // Disable sorting on the `end` event
                onEnd: function (evt) {
                    this.option("disabled", true);
                },
            });

            // Re-enable sorting on the `htmx:afterSwap` event
            sortable.addEventListener("htmx:afterSwap", function () {
                sortableInstance.option("disabled", false);
            });
        });

        _.each(document.querySelectorAll('[data-bs-toggle="tooltip"]'), function (el) {
            new bootstrap.Tooltip(el);
        });
    });
    document.body.addEventListener('htmx:afterRequest', function (evt) {
        if (evt.detail.elt.classList.contains('htmx-request')) {
            evt.detail.elt.classList.remove('htmx-request');
        }
    });
    document.body.addEventListener('htmx:responseError', function (evt) {
        let modal = new bootstrap.Modal(document.getElementById('htmxRequestErrorModal'));
        window.dispatchEvent(new CustomEvent('updateHtmxRequestErrorModal', {
            detail: {
                errorCode: evt.detail.xhr.status,
                errorText: evt.detail.xhr.statusText,
            },
        }));
        modal.show();
    });
    document.body.addEventListener('htmx:timeout', function (evt) {
        console.log("a request timed out");
        console.log(evt);
    });
    var cleanDataOffcanvas = document.getElementById('editOffcanvas');
    cleanDataOffcanvas.addEventListener('hidden.bs.offcanvas', function () {
        if (document.getElementById('numChangesDCAlert')) {
            var numChangesDCAlert = bootstrap.Alert.getOrCreateInstance('#numChangesDCAlert');
            numChangesDCAlert.close();
        }
    });
});
