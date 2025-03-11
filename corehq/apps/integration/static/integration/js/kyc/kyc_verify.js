import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import $ from "jquery";
import { multiCheckboxSelectionHandler } from "integration/js/checkbox_selection_handler";

function updateVerifyButton(selectedIds) {
    const $verifyBtn = $('#verify-selected-btn');
    const $verifyAll = $verifyBtn.find('span:first');
    const $verifySelected = $verifyBtn.find('span:last');

    let verifyBtnVals = JSON.parse($verifyBtn.attr('hx-vals'));
    if (selectedIds.length > 0) {
        $verifyAll.addClass('d-none');
        $verifySelected.removeClass('d-none');
        verifyBtnVals['verify_all'] = false;
    } else {
        $verifyAll.removeClass('d-none');
        $verifySelected.addClass('d-none');
        verifyBtnVals['verify_all'] = true;
    }
    verifyBtnVals['selected_ids'] = selectedIds;
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
    if (requestPath.includes('/kyc/verify/table/') && method === 'get' && event.detail.successful) {
        handler.selectedIds = [];
        updateVerifyButton([]);
    }
});
