import "commcarehq";
import "hqwebapp/js/htmx_base";
import Alpine from 'alpinejs';
import 'reports/js/bootstrap5/base';
import $ from "jquery";
import { multiCheckboxSelectionHandler } from "integration/js/checkbox_selection_handler";
import htmx from 'htmx.org';

Alpine.data('caseCreatedDateRangeFilter', (startdate, enddate) => ({
    startdate,
    enddate,
    init() {
        const $picker = $(this.$refs.picker);
        $picker.createDateRangePicker(
            {
                last_7_days: gettext('Last 7 Days'),
                last_month: gettext('Last Month'),
                last_30_days: gettext('Last 30 Days'),
            },
            $picker.getDateRangeSeparator(),
            this.startdate,
            this.enddate,
        );
        $picker.on('apply.daterangepicker', (ev, picker) => {
            this.startdate = picker.startDate.format('YYYY-MM-DD');
            this.enddate = picker.endDate.format('YYYY-MM-DD');
        });
        // The library's built-in clear (in daterangepicker.config.js) is gated on the
        // picker having a 'name' attribute, which we omit to keep its value out of the URL.
        $picker.on('cancel.daterangepicker', () => {
            this.startdate = '';
            this.enddate = '';
        });
    },
}));

Alpine.start();


function updateVerifyAndRevertButton(selectedIds) {
    updateVerifyButton(selectedIds);
    updateRevertVerificationButton(selectedIds);
}

function updateVerifyButton(selectedIds) {
    const $verifySelectedBtn = $('#verify-selected-btn');
    const $verifyConfirmationBtn = $('#verify-confirmation-btn');

    let verifyBtnVals = JSON.parse($verifyConfirmationBtn.attr('hx-vals'));

    $verifySelectedBtn.prop('disabled', !(selectedIds.length));
    verifyBtnVals['selected_ids'] = selectedIds;
    $verifyConfirmationBtn.attr('hx-vals', JSON.stringify(verifyBtnVals));
}

function updateRevertVerificationButton(selectedIds) {
    const $revertVerificationBtn = $('#revert-verification-selected-btn');
    const $revertVerificationConfirmationBtn = $('#revert-verification-confirmation-btn');

    let revertVerificationVals = JSON.parse($revertVerificationConfirmationBtn.attr('hx-vals'));

    $revertVerificationBtn.prop('disabled', !(selectedIds.length));
    revertVerificationVals['selected_ids'] = selectedIds;
    $revertVerificationConfirmationBtn.attr('hx-vals', JSON.stringify(revertVerificationVals));
}

const handler = new multiCheckboxSelectionHandler('selection', 'select_all', updateVerifyAndRevertButton);
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
        updateVerifyAndRevertButton([]);
    } else if (method === 'post') {
        const endpoint = requestPath + window.location.search;
        // The timeout is to allow the verification request enough time to update the affected cases in ES before
        // doing a refresh
        setTimeout(() => {
            htmx.ajax('GET', endpoint, {target: '#payment-verify-table'});
        }, 3000);
    }
});
