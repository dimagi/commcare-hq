
hqDefine('repeaters/js/bootstrap5/repeat_record_report', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'ace-builds/src-min-noconflict/ace',
    'ace-builds/src-min-noconflict/mode-json',
    'ace-builds/src-min-noconflict/mode-xml',
    'reports/js/bootstrap5/base',
    'reports/js/bootstrap5/tabular',
    'commcarehq',
], function (
    $,
    initialPageData,
    ace,
) {
    const selectAllCheckbox = document.getElementById('select-all-checkbox'),
        selectedPageInfo = document.getElementById('selected-page-info'),
        selectedTableInfo = document.getElementById('selected-table-info'),
        selectTableButton = document.getElementById('select-table-button'),
        items = document.getElementsByName('record_ids'),
        cancelButton = document.getElementById('cancel-button'),
        requeueButton = document.getElementById('requeue-button'),
        resendButton = document.getElementById('resend-button'),
        $popUp = $('#are-you-sure'),
        $confirmButton = $('#confirm-button');

    var selectedEntireTable = false;

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

        $('#resend-button').on('click', function () {
            setAction('resend');
            performAction('resend');
        });

        $('#cancel-button').on('click', function () {
            setAction('cancel');
            performAction('cancel');
        });

        $('#requeue-button').on('click', function () {
            setAction('requeue');
            performAction('requeue');
        });

        $('#confirm-button').on('click', function () {
            const requestBody = getRequestBody(),
                action = getAction();
            let $btn;

            $popUp.modal('hide');  /* todo B5: plugin:modal */
            if (action === 'resend') {
                $btn = $('#resend-button');
                $btn.disableButton();
                postResend($btn, requestBody);
            } else if (action === 'cancel') {
                $btn = $('#cancel-button');
                $btn.disableButton();
                postOther($btn, requestBody, action);
            } else if (action === 'requeue') {
                $btn = $('#requeue-button');
                $btn.disableButton();
                postOther($btn, requestBody, action);
            }
        });

        function performAction(action) {
            const checkedRecords = getCheckedRecords();
            if (selectedEntireTable) {
                hideAllWarnings();
                $popUp.modal('show');  /* todo B5: plugin:modal */
            } else if (checkedRecords.length > 0) {
                if (isActionPossibleForCheckedItems(action, checkedRecords)) {
                    hideAllWarnings();
                    $popUp.modal('show');  /* todo B5: plugin:modal */
                } else {
                    showWarning('not-allowed');
                }
            } else {
                showWarning('no-selection');
            }
        }

        function getCheckedRecords() {
            return $.find('input[type=checkbox][name=record_ids]:checked');
        }

        function isActionPossibleForCheckedItems(action, checkedItems) {
            for (const item of checkedItems) {
                const isQueued = item.getAttribute('is_queued');
                if (isQueued == 'false' && action == 'cancel') {
                    return false;
                } else if (isQueued == 'true' && ['resend', 'requeue'].includes(action)) {
                    return false;
                }
            }
            return true;
        }

        function getRequestBody() {
            if (selectedEntireTable) {
                return getBulkSelectionProperties();
            } else {
                return getRecordIds();
            }
        }

        function getBulkSelectionProperties() {
            return {
                payload_id: initialPageData.get('payload_id'),
                repeater_id: initialPageData.get('repeater_id'),
                state: initialPageData.get('state'),
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
            if (selectAllCheckbox.checked) {
                toggleItems(true);
                selectedPageInfo.classList.remove('hide');
                const pageSize = document.querySelectorAll("#report_table_repeat_record_report tbody tr").length
                document.getElementById("selected-page-count").innerText = pageSize
                if (pageSize >= initialPageData.get('total')) {
                    selectTableButton.classList.add('hide');
                } else {
                    selectTableButton.classList.remove('hide');
                }
            } else {
                toggleItems(false);
                selectedPageInfo.classList.add('hide');
                // just in case
                selectedTableInfo.classList.add('hide');
                selectedEntireTable = false;
            }
            updateActionButtons();
        });

        $('#report-content').on('click', '.record-checkbox', function() {
            resetTableSelections();
            updateActionButtons();
        });

        $("#select-table-button").click(function() {
            selectedEntireTable = true;
            selectedPageInfo.classList.add('hide');
            selectedTableInfo.classList.remove('hide');
            updateActionButtons()
        });

        $("#clear-table-selection").click(function() {
            toggleItems(false);
            resetTableSelections();
            updateActionButtons()
        });

        $('body').on('DOMNodeInserted', 'tbody', function () {
            for (const item of items) {
                $(item).on('click', updateActionButtons);
            }
        });

        function toggleItems(checked) {
            for (const item of items) {
                if (item.type === 'checkbox') {
                    item.checked = checked;
                }
            }
        }

        function updateActionButtons() {
            const checkedRecords = getCheckedRecords();
            if (checkedRecords.length == 0) {
                resendButton.disabled = true;
                requeueButton.disabled = true;
                cancelButton.disabled = true;
                return;
            }

            const containsQueuedRecords = checkedRecords.some(record => {
                return record.getAttribute('is_queued') == true;
            });

            // default to no-op on cancelling a batch of records
            // that contain some already cancelled records
            // versus allowing no-op when queueing already queued
            // records
            if (containsQueuedRecords) {
                resendButton.disabled = true;
                requeueButton.disabled = true;
                cancelButton.disabled = false;
            } else {
                resendButton.disabled = false;
                requeueButton.disabled = false;
                cancelButton.disabled = true;
            }
        }

        function resetTableSelections() {
            selectedEntireTable = false;
            selectAllCheckbox.checked = false;
            selectedPageInfo.classList.add('hide');
            selectedTableInfo.classList.add('hide');
        }
    });
});
