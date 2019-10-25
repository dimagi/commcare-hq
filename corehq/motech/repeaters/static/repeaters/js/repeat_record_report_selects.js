var items = document.getElementsByName('xform_ids');
var all = document.getElementById('select_all');
var all_cancel = document.getElementById('cancel_all');
var all_requeue = document.getElementById('requeue_all');

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
    } else {
        unSelectItems();
    }
}

function selectRequeue() {
    unSelectItems();
    uncheck(all, all_cancel);
    if (all_requeue.checked) {
        checkMultipleItems('requeue');
    }
}

function selectCallable() {
    unSelectItems();
    uncheck(all, all_requeue);
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
