'use strict';

hqDefine("prototype/js/data_cleaning",[
    'underscore',
    'sortablejs',
    'es6!hqwebapp/js/bootstrap5_loader',
    'prototype/js/htmx_action',  // support hx-action attributes
], function (_, Sortable, bootstrap) {
    let htmx = window.htmx;
    htmx.onLoad(function (content) {
        let sortables = content.querySelectorAll(".sortable");
        for (let i = 0; i < sortables.length; i++) {
            let sortable = sortables[i];
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
        }
    });
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        if (evt.detail.elt.dataset.refreshTable) {
            htmx.trigger(evt.detail.elt.dataset.refreshTable, 'refreshTable');
        }
    });
    document.body.addEventListener('htmx:beforeSend', function (evt) {
        if (evt.detail.elt.dataset.selectAll) {
            // Transfer "select all" checkbox event from the table header checkbox to all checkboxes
            // on client side by triggering the click event that Alpine is bound to
            let isSelected = evt.detail.elt.checked;
            evt.detail.requestConfig.parameters.pageRowIds = _.map(
                document.getElementsByClassName('js-select-row'), function (el) {
                    el.checked = isSelected;
                    htmx.trigger(el, 'click');
                    return el.value;
                });
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
});
