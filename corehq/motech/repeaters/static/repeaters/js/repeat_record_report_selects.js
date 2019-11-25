var items = document.getElementsByName('xform_ids'),
    all = document.getElementById('select_all'),
    all_cancel = document.getElementById('cancel_all'),
    all_requeue = document.getElementById('requeue_all'),
    button_cancel = document.getElementById('cancelAll'),
    button_requeue = document.getElementById('requeueAll');

function selectItems() {
    for (var i = 0; i < items.length; i++) {
        if (items[i].type == 'checkbox')
            items[i].checked = true;
    }
}

function unSelectItems() {
    for (var i = 0; i < items.length; i++) {
        if (items[i].type == 'checkbox')
            items[i].checked = false;
    }
}

function selectItemsForAllButton() {
    selectItems();
    uncheckSelects();
}

function unSelectItemsForNoneButton() {
    unSelectItems();
    uncheckSelects();
}

function selectAll() {
    if (all.checked) {
        selectItems();
        uncheck(all_cancel, all_requeue);
        turnOffCancelRequeue();
    } else {
        unSelectItems();
        turnOnCancelRequeue();
    }
}

function selectRequeue() {
    unSelectItems();
    uncheck(all, all_cancel);
    turnOnCancelRequeue();
    button_cancel.disabled = true;
    if (all_requeue.checked) {
        checkMultipleItems('requeue');
    }
}

function selectCallable() {
    unSelectItems();
    uncheck(all, all_requeue);
    turnOnCancelRequeue();
    button_requeue.disabled = true;
    if (all_cancel.checked) {
        checkMultipleItems('cancel');
    }
}

function uncheck(checkbox1, checkbox2) {
    checkbox1.checked = false;
    checkbox2.checked = false;
}

function uncheckSelects() {
    all.checked = false;
    all_cancel.checked = false;
    all_requeue.checked = false;
}

function turnOffCancelRequeue() {
    button_cancel.disabled = true;
    button_requeue.disabled = true;
}

function turnOnCancelRequeue() {
    button_cancel.disabled = false;
    button_requeue.disabled = false;
}

function checkMultipleItems(action) {
    for (var i = 0; i < items.length; i++) {
        var id = items[i].value;
        var query = '[data-record-id="' + id + '"][class="btn btn-default '+ action +'-record-payload"]';
        var button = document.querySelector(query);
        if (button != null && items[i].type == 'checkbox') {
            if (items[i].checked)
                items[i].checked = false;
            else
                items[i].checked = true;
        }
    }
}
