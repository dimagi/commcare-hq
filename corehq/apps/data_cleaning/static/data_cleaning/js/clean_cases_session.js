import 'commcarehq';
import { Modal } from 'bootstrap5';
import 'hqwebapp/js/htmx_base';
import 'hqwebapp/js/htmx_utils/hq_hx_select_all';
import 'hqwebapp/js/alpinejs/directives/select2';
import 'hqwebapp/js/alpinejs/directives/report_select2';
import 'hqwebapp/js/alpinejs/directives/datepicker';
import 'hqwebapp/js/alpinejs/directives/htmx_sortable';
import 'hqwebapp/js/alpinejs/directives/tooltip';
import 'data_cleaning/js/directives/dynamic_options_select2';

import wiggleButton from 'hqwebapp/js/alpinejs/components/wiggle_button';
Alpine.data('wiggleButtonModel', wiggleButton);

Alpine.store('isCleaningAllowed', false);
Alpine.store('showWhitespaces', false);
Alpine.store('editDetails', {
    isSessionAtChangeLimit: false,
    isUndoMultiple: false,
    update(details) {
        this.isSessionAtChangeLimit = details.isSessionAtChangeLimit;
        this.isUndoMultiple = details.isUndoMultiple;
    },
});

import Alpine from 'alpinejs';
Alpine.start();

document.body.addEventListener("showDataCleaningModal", function (event) {
    const modal = new Modal(event.detail.elt);
    modal.show();
});

document.body.addEventListener("updateEditDetails", function (event) {
    Alpine.store('editDetails').update(event.detail.editDetails);
});
