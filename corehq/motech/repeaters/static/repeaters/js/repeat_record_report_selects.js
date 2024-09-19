'use strict';
hqDefine('repeaters/js/repeat_record_report_selects', function () {
    const items = document.getElementsByName('xform_ids'),
        selectAll = document.getElementById('select-all'),
        selectPending = document.getElementById('select-pending'),
        selectCancelled = document.getElementById('select-cancelled'),
        selectFailed = document.getElementById('select-failed'),
        selectInvalid = document.getElementById('select-invalid'),
        buttonCancel = document.getElementById('cancel-all-button'),
        buttonRequeue = document.getElementById('requeue-all-button');

    $('#all').on('click', function () {
        selectItems();
        uncheckSelects();
    });

    $('#none').on('click', function () {
        unSelectItems();
        uncheckSelects();
    });

    $('#select-all').on('click', function () {
        if (selectAll.checked) {
            selectItems();
            const checkboxesToDisable = [selectPending, selectCancelled, selectFailed, selectInvalid];
            uncheck(checkboxesToDisable);
            turnOffCancelRequeue();
        } else {
            unSelectItems();
            turnOnCancelRequeue();
        }
    });

    $('#select-pending').on('click', function () {
        unSelectItems();
        const checkboxesToDisable = [selectAll, selectCancelled, selectFailed, selectInvalid];
        uncheck(checkboxesToDisable);
        turnOnCancelRequeue();
        if (selectPending.checked) {
            buttonRequeue.disabled = true;
            checkMultipleItems('cancel');
        } else {
            buttonRequeue.disabled = false;
        }
    });

    $('#select-cancelled').on('click', function () {
        unSelectItems();
        const checkboxesToDisable = [selectAll, selectPending, selectFailed, selectInvalid];
        uncheck(checkboxesToDisable);
        turnOnCancelRequeue();
        if (selectCancelled.checked) {
            buttonCancel.disabled = true;
            checkMultipleItems('requeue');
        } else {
            buttonCancel.disabled = false;
        }
    });

    $('#select-failed').on('click', function () {
        unSelectItems();
        const checkboxesToDisable = [selectAll, selectPending, selectCancelled, selectInvalid];
        uncheck(checkboxesToDisable);
        turnOnCancelRequeue();
        if (selectFailed.checked) {
            buttonRequeue.disabled = true;
            checkMultipleItems('cancel'); // TODO: this doesn't work for failed items, since we don't have a way to identify failed payloads in html
        } else {
            buttonRequeue.disabled = false;
        }
    });

    $('#select-invalid').on('click', function () {
        unSelectItems();
        const checkboxesToDisable = [selectAll, selectPending, selectFailed];
        uncheck(checkboxesToDisable);
        turnOnCancelRequeue();
        if (selectInvalid.checked) {
            buttonCancel.disabled = true;
            checkMultipleItems('requeue'); // TODO: this doesn't work for invalid items, since we don't have a way to identify invalid payloads in html
        } else {
            buttonCancel.disabled = false;
        }
    });

    $('body').on('DOMNodeInserted', 'tbody', function () {
        for (const item of items) {
            $(item).on('click', uncheckSelects);
        }
    });

    function selectItems() {
        for (const item of items) {
            if (item.type === 'checkbox') {
                item.checked = true;
            }
        }
    }

    function unSelectItems() {
        for (const item of items) {
            if (item.type === 'checkbox') {
                item.checked = false;
            }
        }
    }

    function uncheck(checkboxes) {
        for (const checkbox of checkboxes) {
            checkbox.checked = false;
        }
    }

    function uncheckSelects() {
        selectAll.checked = false;
        selectPending.checked = false;
        selectCancelled.checked = false;
        selectFailed.checked = false;
        selectInvalid.checked = false;
        turnOnCancelRequeue();
    }

    function turnOffCancelRequeue() {
        buttonCancel.disabled = true;
        buttonRequeue.disabled = true;
    }

    function turnOnCancelRequeue() {
        buttonCancel.disabled = false;
        buttonRequeue.disabled = false;
    }

    function checkMultipleItems(action) {
        for (const item of items) {
            const id = item.getAttribute('data-id');
            const query = `[data-record-id="${id}"][class="btn btn-default ${action}-record-payload"]`;
            const button = document.querySelector(query);
            if (!!button && item.type === 'checkbox') {
                if (item.checked) {
                    item.checked = false;
                } else {
                    item.checked = true;
                }
            }
        }
    }
});
