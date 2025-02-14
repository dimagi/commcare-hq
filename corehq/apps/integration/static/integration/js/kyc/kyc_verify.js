import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import $ from "jquery";


let selectedUsers = [];

$(document).on('change', 'input[name="selection"]', function () {
    const rowId = $(this).val();
    const isChecked = $(this).prop('checked');
    if (isChecked) {
        selectedUsers.push(rowId);
    } else {
        selectedUsers = selectedUsers.filter(id => id !== rowId);
    }
    updateVerifyButton(selectedUsers.length);
    updateSelectAllCheckbox(selectedUsers.length);
});

$(document).on('change', 'input[name="select_all"]', function () {
    const isChecked = $(this).prop('checked');

    const $rowCheckboxes = $('input[name="selection"]:not(:disabled)');
    $rowCheckboxes.prop('checked', isChecked);

    if (isChecked) {
        selectedUsers = $rowCheckboxes.map(function () {
            return $(this).val();
        }).get();
    } else {
        selectedUsers = [];
    }
    updateVerifyButton(selectedUsers.length);
});

function updateVerifyButton(selectedCount) {
    const $verifyBtn = $('#verify-selected-btn');
    const $verifyAll = $verifyBtn.find('span:first');
    const $verifySelected = $verifyBtn.find('span:last');

    let verifyBtnVals = JSON.parse($verifyBtn.attr('hx-vals'));
    if (selectedCount > 0) {
        $verifyAll.addClass('d-none');
        $verifySelected.removeClass('d-none');
        verifyBtnVals['selected_ids'] = selectedUsers;
        verifyBtnVals['verify_all'] = false;
    } else {
        $verifyAll.removeClass('d-none');
        $verifySelected.addClass('d-none');
        verifyBtnVals['selected_ids'] = [];
        verifyBtnVals['verify_all'] = true;
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