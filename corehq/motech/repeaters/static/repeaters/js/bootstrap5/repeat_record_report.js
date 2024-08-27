/* globals ace */
'use strict';
hqDefine('repeaters/js/bootstrap5/repeat_record_report', function () {
    const initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        selectAll = document.getElementById('select-all'),
        selectPending = document.getElementById('select-pending'),
        selectCancelled = document.getElementById('select-cancelled'),
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
                        </td></tr>`
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

            postResend($btn, recordId);
        });

        $('#resend-all-button').on('click', function () {
            setAction('resend');
            performAction('resend');
        });

        $('#report-content').on('click', '.cancel-record-payload', function () {
            const $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            postOther($btn, recordId, 'cancel');
        });

        $('#cancel-all-button').on('click', function () {
            setAction('cancel');
            performAction('cancel');
        });

        $('#report-content').on('click', '.requeue-record-payload', function () {
            const $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            postOther($btn, recordId, 'requeue');
        });

        $('#requeue-all-button').on('click', function () {
            setAction('requeue');
            performAction('requeue');
        });

        $('#confirm-button').on('click', function () {
            const requestBody = getRequestBody(),
                action = getAction();
            let $btn;

            $popUp.modal('hide');  /* todo B5: plugin:modal */
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
            if (bulkSelection || areRecordsChecked()) {
                if (bulkSelection) { setFlag(bulkSelection); }
                // only applies to checked items, not bulk selections
                // leaving as is to preserve behavior
                if (isActionPossibleForCheckedItems(action)) {
                    hideAllWarnings();
                    $popUp.modal('show');  /* todo B5: plugin:modal */
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

        function areRecordsChecked() {
            const items = document.getElementsByName('xform_ids');
            for (const item of items) {
                if (item.checked) {
                    return true;
                }
            }
            return false;
        }

        function isActionPossibleForCheckedItems(action) {
            const items = document.getElementsByName('xform_ids');
            for (const item of items) {
                if (item.checked) {
                    const id = item.getAttribute('data-id');
                    const query = `[data-record-id="${id}"][class="btn btn-default ${action}-record-payload"]`;
                    const button = document.querySelector(query);
                    if (!button) {
                        return false;
                    }
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
            const recordEls = document.getElementsByName('xform_ids');
            let recordIds = '';
            for (const record of recordEls) {
                if (record.type === 'checkbox' && record.checked) {
                    recordIds += record.getAttribute('data-id') + ' ';
                }
            }
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
                        $('#payload-error-modal').modal('show');  /* todo B5: plugin:modal */
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
    });
});
