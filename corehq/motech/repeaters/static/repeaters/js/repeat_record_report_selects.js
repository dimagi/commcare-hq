
hqDefine('repeaters/js/repeat_record_report_selects', ['jquery'], function ($) {
    const items = document.getElementsByName('xform_ids'),
        selectAll = document.getElementById('select-all'),
        selectPending = document.getElementById('select-pending'),
        selectCancelled = document.getElementById('select-cancelled'),
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
            uncheck(selectPending, selectCancelled);
            turnOffCancelRequeue();
        } else {
            unSelectItems();
            turnOnCancelRequeue();
        }
    });

    $('#select-pending').on('click', function () {
        unSelectItems();
        uncheck(selectAll, selectCancelled);
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
        uncheck(selectAll, selectPending);
        turnOnCancelRequeue();
        if (selectCancelled.checked) {
            buttonCancel.disabled = true;
            checkMultipleItems('requeue');
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

    function uncheck(checkbox1, checkbox2) {
        checkbox1.checked = false;
        checkbox2.checked = false;
    }

    function uncheckSelects() {
        selectAll.checked = false;
        selectPending.checked = false;
        selectCancelled.checked = false;
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
