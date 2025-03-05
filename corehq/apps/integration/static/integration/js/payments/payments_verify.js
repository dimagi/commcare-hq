import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import $ from "jquery";
import { multiCheckboxSelectionHandler } from "integration/js/checkbox_selection_handler";


function updateVerifyButton(selectedIds) {
    const $verifyBtn = $('#verify-selected-btn');
    let verifyBtnVals = JSON.parse($verifyBtn.attr('hx-vals'));

    if (selectedIds.length > 0) {
        $verifyBtn.prop('disabled', false);
        verifyBtnVals['selected_ids'] = selectedIds;
    } else {
        $verifyBtn.prop('disabled', true);
        verifyBtnVals['selected_ids'] = [];
    }
    $verifyBtn.attr('hx-vals', JSON.stringify(verifyBtnVals));
}

const handler = new multiCheckboxSelectionHandler('selection', 'select_all', updateVerifyButton);
$(function () {
    handler.init();
});

$(document).on('htmx:afterRequest', function (event) {
    // Reset on pagination as the table is recreated after htmx request
    const requestPath = event.detail.requestConfig.path;
    const method = event.detail.requestConfig.verb;
    if (requestPath.includes('/payments/verify/table/') && method === 'get' && event.detail.successful === true) {
        handler.selectedIds = [];
        updateVerifyButton([]);
    }
});
