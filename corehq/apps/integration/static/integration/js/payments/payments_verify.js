import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import $ from "jquery";


let selectedIds = [];

$(document).on('change', 'input[name="selection"]', function () {
    const rowId = $(this).val();
    const isChecked = $(this).prop('checked');
    if (isChecked) {
        selectedIds.push(rowId);
    } else {
        selectedIds = selectedIds.filter(id => id !== rowId);
    }
    updateVerifyButton(selectedIds.length);
    updateSelectAllCheckbox(selectedIds.length);
});

$(document).on('change', 'input[name="select_all"]', function () {
    const isChecked = $(this).prop('checked');

    const $rowCheckboxes = $('input[name="selection"]:not(:disabled)');
    $rowCheckboxes.prop('checked', isChecked);

    if (isChecked) {
        selectedIds = $rowCheckboxes.map(function () {
            return $(this).val();
        }).get();
    } else {
        selectedIds = [];
    }
    updateVerifyButton(selectedIds.length);
});

function updateVerifyButton(selectedCount) {
    const $verifyBtn = $('#verify-selected-btn');
    let verifyBtnVals = JSON.parse($verifyBtn.attr('hx-vals'));

    if (selectedCount > 0) {
        $verifyBtn.prop('disabled', false);
        verifyBtnVals['selected_ids'] = selectedIds;
    } else {
        $verifyBtn.prop('disabled', true);
        verifyBtnVals['selected_ids'] = [];
    }
    $verifyBtn.attr('hx-vals', JSON.stringify(verifyBtnVals));
}

function updateSelectAllCheckbox(selectedCount) {
    if (selectedCount > 0) {
        return;
    }
    const $selectAll = $('input[name="select_all"]');
    $selectAll.prop('checked', false);
}
