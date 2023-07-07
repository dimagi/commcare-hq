/* globals ace */
hqDefine('repeaters/js/repeat_record_report', function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        selectAll = document.getElementById('select-all'),
        cancelAll = document.getElementById('cancel-all'),
        requeueAll = document.getElementById('requeue-all'),
        $popUp = $('#are-you-sure');
        $confirmButton = $('#confirm-button');

    $(function () {
        $('#report-content').on('click', '.toggle-next-attempt', function (e) {
            $(this).nextAll('.record-attempt').toggle();
            e.preventDefault();
        });
        $('#report-content').on('click', '.view-attempts-btn', function () {
            const recordId = $(this).data().recordId;

            // Clear out previous error message banner, if it exists
            $(`#${recordId}.attempt-error`).remove();

            let $attemptTable = $(`#${recordId}.attempt-row`);
            if ($attemptTable.length) {
                // There should only be one table per record
                $($attemptTable[0]).toggle();
                return;
            }

            const $row = $(this).closest('tr');
            $.get({
                url: initialPageData.reverse("repeat_record"),
                data: { record_id: recordId },
                success: function (data) {
                    // User might have clicked to fetch attempts while previous fetch is busy,
                    // so skip if one already exists
                    $attemptTable = $(`#${recordId}.attempt-row`);
                    if (!$attemptTable.length) {
                        $row.after(data.attempts);
                    }
                },
                error: function (data) {
                    const defaultText = gettext('Failed to fetch attempts');
                    const errorMessage = data.responseJSON ? data.responseJSON.error : null;
                    $row.after(
                        `<tr id="${recordId}" class="attempt-error"><td colspan="10">
                            <div class="alert alert-danger">${errorMessage || defaultText}</div>
                        </td></tr>`
                    );
                },
            });
        });
        var editor = null;
        $('#view-record-payload-modal').on('shown.bs.modal', function (event) {
            var recordData = $(event.relatedTarget).data(),
                $modal = $(this);

            $.get({
                url: initialPageData.reverse("repeat_record"),
                data: { record_id: recordData.recordId },
                success: function (data) {
                    var $payload = $modal.find('.payload'),
                        contentType = data.content_type;

                    if (editor === null) {
                        editor = ace.edit(
                            $payload.get(0),
                            {
                                showPrintMargin: false,
                                maxLines: 40,
                                minLines: 3,
                                fontSize: 14,
                                wrap: true,
                                useWorker: false,
                            }
                        );
                        editor.setReadOnly(true);
                    }
                    if (contentType === 'text/xml') {
                        editor.session.setMode('ace/mode/xml');
                    } else if (contentType === 'application/json') {
                        editor.session.setMode('ace/mode/json');
                    }
                    editor.session.setValue(data.payload);
                },
                error: function (data) {
                    var defaultText = gettext('Failed to fetch payload'),
                        errorMessage = data.responseJSON ? data.responseJSON.error : null;

                    $modal.find('.modal-body').text(errorMessage || defaultText);
                },
            });
        });

        $('#view-record-payload-modal').on('hide.bs.modal', function () {
            if (editor) {
                editor.session.setValue('');
            }
        });

        $('#report-content').on('click', '.resend-record-payload', function () {
            var $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            postResend($btn, recordId);
        });

        $('#resend-all-button').on('click', function () {
            setAction('resend');
            performAction('resend');
        });

        $('#report-content').on('click', '.cancel-record-payload', function () {
            var $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            postOther($btn, recordId, 'cancel');
        });

        $('#cancel-all-button').on('click', function () {
            setAction('cancel');
            performAction('cancel');
        });

        $('#report-content').on('click', '.requeue-record-payload', function () {
            var $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            postOther($btn, recordId, 'requeue');
        });

        $('#requeue-all-button').on('click', function () {
            setAction('requeue');
            performAction('requeue');
        });

        $('#confirm-button').on('click', function () {
            var itemsToSend = getCheckboxes(), action = getAction(), $btn;

            $popUp.modal('hide');
            if (action == 'resend') {
                $btn = $('#resend-all-button');
                $btn.disableButton();
                postResend($btn, itemsToSend);
            } else if (action == 'cancel') {
                $btn = $('#cancel-all-button');
                $btn.disableButton();
                postOther($btn, itemsToSend, action);
            } else if (action == 'requeue') {
                $btn = $('#requeue-all-button');
                $btn.disableButton();
                postOther($btn, itemsToSend, action);
            }
        });

        function performAction(action) {
            if (isAnythingChecked()) {
                if (isActionPossibleForCheckedItems(action)) {
                    $('#warning').addClass('hide');
                    $('#not-allowed').addClass('hide');
                    $popUp.modal('show');
                } else {
                    $('#warning').addClass('hide');
                    $('#not-allowed').removeClass('hide');
                }
            } else {
                $('#warning').removeClass('hide');
                $('#not-allowed').addClass('hide');
            }
        }

        function isAnythingChecked() {
            var items = document.getElementsByName('xform_ids');

            if (selectAll.checked) {
                setFlag('select_all');
                return true;
            } else if (cancelAll.checked) {
                setFlag('cancel_all');
                return true;
            } else if (requeueAll.checked) {
                setFlag('requeue_all');
                return true;
            }

            for (var i = 0; i < items.length; i++) {
                if (items[i].checked) {
                    return true;
                }
            }

            return false;
        }

        function isActionPossibleForCheckedItems(action) {
            var items = document.getElementsByName('xform_ids');
            for (var i = 0; i < items.length; i++) {
                if (items[i].checked) {
                    var id = items[i].getAttribute('data-id');
                    var query = '[data-record-id="' + id + '"][class="btn btn-default ' + action + '-record-payload"]';
                    var button = document.querySelector(query);
                    if (button == null) {
                        return false;
                    }
                }
            }

            return true;
        }

        function getCheckboxes() {
            if (selectAll.checked) {
                return selectAll.getAttribute('data-id');
            } else if (cancelAll.checked) {
                return cancelAll.getAttribute('data-id');
            } else if (requeueAll.checked) {
                return requeueAll.getAttribute('data-id');
            } else {
                var items = document.getElementsByName('xform_ids'),
                    itemsToSend = '';
                for (var i = 0; i < items.length; i++) {
                    if (items[i].type == 'checkbox' && items[i].checked == true) {
                        itemsToSend += items[i].getAttribute('data-id') + ' '
                    }
                }

                return itemsToSend;
            }
        }

        function postResend(btn, arg) {
            $.post({
                url: initialPageData.reverse("repeat_record"),
                data: {
                    record_id: arg,
                    flag: getFlag(),
                },
                success: function (data) {
                    btn.removeSpinnerFromButton();
                    if (data.success) {
                        btn.text(gettext('Success!'));
                        btn.addClass('btn-success');
                    } else {
                        btn.text(gettext('Failed'));
                        btn.addClass('btn-danger');
                        $('#payload-error-modal').modal('show');
                        $('#payload-error-modal .error-message').text(data.failure_reason);
                    }
                },
                error: function () {
                    btn.removeSpinnerFromButton();
                    btn.text(gettext('Failed to send'));
                    btn.addClass('btn-danger');
                },
            });
        }

        function postOther(btn, arg, action) {
            $.post({
                url: initialPageData.reverse(action + '_repeat_record'),
                data: {
                    record_id: arg,
                    flag: getFlag(),
                },
                success: function () {
                    btn.removeSpinnerFromButton();
                    btn.text(gettext('Success!'));
                    btn.addClass('btn-success');
                },
                error: function () {
                    btn.removeSpinnerFromButton();
                    btn.text(gettext('Failed to cancel'));
                    btn.addClass('btn-danger');
                },
            });
        }

        function setAction(action) {
            $confirmButton.attr('data-action', action);
        }

        function getAction() {
            return $confirmButton.attr('data-action');
        }

        function setFlag(flag) {
            $confirmButton.attr('data-flag', flag);
        }

        function getFlag() {
            return $confirmButton.attr('data-flag');
        }
    });
});
