
hqDefine('repeaters/js/bootstrap3/repeat_record_report', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'ace-builds/src-min-noconflict/ace',
    'ace-builds/src-min-noconflict/mode-json',
    'ace-builds/src-min-noconflict/mode-xml',
    'reports/js/bootstrap3/base',
    'reports/js/bootstrap3/tabular',
    'commcarehq',
], function (
    $,
    initialPageData,
    ace,
) {
    const selectAll = document.getElementById('select-all'),
        selectAllCheckbox = document.getElementById('select-all-checkbox'),
        selectPending = document.getElementById('select-pending'),
        selectCancelled = document.getElementById('select-cancelled'),
        items = document.getElementsByName('xform_ids'),
        buttonCancel = document.getElementById('cancel-all-button'),
        buttonRequeue = document.getElementById('requeue-all-button'),
        $popUp = $('#are-you-sure'),
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
                        </td></tr>`,
                    );
                },
            });
        });

        let editor = null;
        $('#view-record-payload-modal').on('shown.bs.modal', function (event) {
            const recordData = $(event.relatedTarget).data(),
                $modal = $(this);

            $.get({
                url: initialPageData.reverse("repeat_record"),
                data: { record_id: recordData.recordId },
                success: function (data) {
                    const $payload = $modal.find('.payload'),
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
                            },
                        );
                        editor.setReadOnly(true);
                    }
                    if (contentType === 'text/xml') {
                        editor.session.setMode('ace/mode/xml');
                    } else if (['application/json', 'application/x-www-form-urlencoded'].includes(contentType)) {
                        editor.session.setMode('ace/mode/json');
                    }
                    editor.session.setValue(data.payload);
                },
                error: function (data) {
                    const defaultText = gettext('Failed to fetch payload'),
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
            const $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            postResend($btn, {'record_id': recordId});
        });

        $('#resend-all-button').on('click', function () {
            setAction('resend');
            performAction('resend');
        });

        $('#report-content').on('click', '.cancel-record-payload', function () {
            const $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            postOther($btn, {'record_id': recordId}, 'cancel');
        });

        $('#cancel-all-button').on('click', function () {
            setAction('cancel');
            performAction('cancel');
        });

        $('#report-content').on('click', '.requeue-record-payload', function () {
            const $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            postOther($btn, {'record_id': recordId}, 'requeue');
        });

        $('#requeue-all-button').on('click', function () {
            setAction('requeue');
            performAction('requeue');
        });

        $('#confirm-button').on('click', function () {
            const requestBody = getRequestBody(),
                action = getAction();
            let $btn;

            $popUp.modal('hide');
            if (action === 'resend') {
                $btn = $('#resend-all-button');
                $btn.disableButton();
                postResend($btn, requestBody);
            } else if (action === 'cancel') {
                $btn = $('#cancel-all-button');
                $btn.disableButton();
                postOther($btn, requestBody, action);
            } else if (action === 'requeue') {
                $btn = $('#requeue-all-button');
                $btn.disableButton();
                postOther($btn, requestBody, action);
            }
        });

        function performAction(action) {
            const bulkSelection = bulkSelectionChecked();
            const checkedRecords = getCheckedRecords();
            if (bulkSelection || checkedRecords.length > 0) {
                if (bulkSelection) { setFlag(bulkSelection); }
                // only applies to checked items, not bulk selections
                // leaving as is to preserve behavior
                if (isActionPossibleForCheckedItems(action, checkedRecords)) {
                    hideAllWarnings();
                    $popUp.modal('show');
                } else {
                    showWarning('not-allowed');
                }
            } else {
                showWarning('no-selection');
            }
        }

        function bulkSelectionChecked() {
            if (selectAll.checked) {
                return 'select_all';
            } else if (selectPending.checked) {
                return 'select_pending';
            } else if (selectCancelled.checked) {
                return 'select_cancelled';
            }
        }

        function getCheckedRecords() {
            return $.find('input[type=checkbox][name=xform_ids]:checked');
        }

        function isActionPossibleForCheckedItems(action, items) {
            for (const item of items) {
                const id = item.getAttribute('data-id');
                const query = `[data-record-id="${id}"][class="btn btn-default ${action}-record-payload"]`;
                const button = document.querySelector(query);
                if (!button) {
                    return false;
                }
            }

            return true;
        }

        function getRequestBody() {
            const bulkSelectors = [selectAll, selectPending, selectCancelled];
            if (bulkSelectors.some(selector => selector.checked)) {
                return getBulkSelectionProperties();
            } else {
                return getRecordIds();
            }
        }

        function getBulkSelectionProperties() {
            return {
                payload_id: initialPageData.get('payload_id'),
                repeater_id: initialPageData.get('repeater_id'),
                flag: getFlag(),
            };
        }

        function getRecordIds() {
            const recordEls = getCheckedRecords();
            const recordIds = recordEls.map(
                record => record.getAttribute('data-id'),
            ).join(' ');
            return {record_id: recordIds};
        }

        function postResend(btn, data) {
            $.post({
                url: initialPageData.reverse("repeat_record"),
                data: data,
                success: function (response) {
                    btn.removeSpinnerFromButton();
                    if (response.success) {
                        btn.text(gettext('Success!'));
                        btn.addClass('btn-success');
                    } else {
                        btn.text(gettext('Failed'));
                        btn.addClass('btn-danger');
                        $('#payload-error-modal').modal('show');
                        $('#payload-error-modal .error-message').text(response.failure_reason);
                    }
                },
                error: function () {
                    btn.removeSpinnerFromButton();
                    btn.text(gettext('Failed to send'));
                    btn.addClass('btn-danger');
                },
            });
        }

        function postOther(btn, data, action) {
            $.post({
                url: initialPageData.reverse(action + '_repeat_record'),
                data: data,
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

        function showWarning(reason) {
            if (reason === 'no-selection') {
                $('#no-selection').removeClass('hide');
                $('#not-allowed').addClass('hide');
            } else if (reason === 'not-allowed') {
                $('#not-allowed').removeClass('hide');
                $('#no-selection').addClass('hide');
            }
        }

        function hideAllWarnings() {
            $('#no-selection').addClass('hide');
            $('#not-allowed').addClass('hide');
        }

        // ----- what was once repeat_record_report_selects.js ------

        $('#select-all-checkbox').on('click', function () {
            toggleItems(selectAllCheckbox.checked);
            uncheckSelects();
        });

        $('#select-all').on('click', function () {
            if (selectAll.checked) {
                toggleItems(true);
                uncheck(selectPending, selectCancelled);
                turnOffCancelRequeue();
            } else {
                toggleItems(false);
                turnOnCancelRequeue();
            }
        });

        $('#select-pending').on('click', function () {
            toggleItems(false);
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
            toggleItems(false);
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

        function toggleItems(checked) {
            for (const item of items) {
                if (item.type === 'checkbox') {
                    item.checked = checked;
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
});
