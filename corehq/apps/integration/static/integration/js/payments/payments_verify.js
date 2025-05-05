import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import 'reports/js/bootstrap5/base';
import $ from "jquery";
import { multiCheckboxSelectionHandler } from "integration/js/checkbox_selection_handler";
import htmx from 'htmx.org';


function updateVerifyButton(selectedIds) {
    const $verifySelectedBtn = $('#verify-selected-btn');
    const $verifyConfirmationBtn = $('#verify-confirmation-btn');

    let verifyBtnVals = JSON.parse($verifyConfirmationBtn.attr('hx-vals'));

    $verifySelectedBtn.prop('disabled', !(selectedIds.length));
    verifyBtnVals['selected_ids'] = selectedIds;
    $verifyConfirmationBtn.attr('hx-vals', JSON.stringify(verifyBtnVals));
}

const handler = new multiCheckboxSelectionHandler('selection', 'select_all', updateVerifyButton);
$(function () {
    handler.init();
});

$(document).on('htmx:afterRequest', function (event) {
    // Reset on pagination as the table is recreated after htmx request
    const requestPath = event.detail.requestConfig.path;
    if (!requestPath.includes('/payments/verify/table/') || !event.detail.successful) {
        return;
    }

    const method = event.detail.requestConfig.verb;
    if (method === 'get') {
        handler.selectedIds = [];
        updateVerifyButton([]);
    } else if (method === 'post') {
        const endpoint = requestPath + window.location.search;
        // The timeout is to allow the verification request enough time to update the affected cases in ES before
        // doing a refresh
        setTimeout(() => {
            htmx.ajax('GET', endpoint, {target: '#payment-verify-table'});
        }, 3000);
    }
});
