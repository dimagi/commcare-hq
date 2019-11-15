/* globals ace */
hqDefine('repeaters/js/repeat_record_report_selects', function() {
    var items = document.getElementsByName('xform_ids'),
        all = document.getElementById('select-all'),
        allCancel = document.getElementById('cancel-all'),
        allRequeue = document.getElementById('requeue-all'),
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
        if (all.checked) {
            selectItems();
            uncheck(allCancel, allRequeue);
            turnOffCancelRequeue();
        } else {
            unSelectItems();
            turnOnCancelRequeue();
        }
    });

    $('#cancel-all').on('click', function () {
        unSelectItems();
        uncheck(all, allRequeue);
        turnOnCancelRequeue();
        if (allCancel.checked) {
            buttonRequeue.disabled = true;
            checkMultipleItems('cancel');
        } else {
            buttonRequeue.disabled = false;
        }
    });

    $('#requeue-all').on('click', function () {
        unSelectItems();
        uncheck(all, allCancel);
        turnOnCancelRequeue();
        if (allRequeue.checked) {
            buttonCancel.disabled = true;
            checkMultipleItems('requeue');
        } else {
            buttonCancel.disabled = false;
        }
    });

    $('body').on('DOMNodeInserted', 'tbody', function () {
      for (var i = 0; i < items.length; i++) {
            $(items[i]).on('click', uncheckSelects);
        }
    });

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

    function uncheck(checkbox1, checkbox2) {
        checkbox1.checked = false;
        checkbox2.checked = false;
    }

    function uncheckSelects() {
        all.checked = false;
        allCancel.checked = false;
        allRequeue.checked = false;
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
        for (var i = 0; i < items.length; i++) {
            var id = items[i].getAttribute('data-id');
            var query = '[data-record-id="' + id + '"][class="btn btn-default ' + action + '-record-payload"]';
            var button = document.querySelector(query);
            if (button != null && items[i].type == 'checkbox') {
                if (items[i].checked) {
                    items[i].checked = false;
                } else {
                    items[i].checked = true;
                }
            }
        }
    }
});
