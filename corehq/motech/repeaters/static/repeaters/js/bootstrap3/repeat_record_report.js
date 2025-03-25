
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

            $popUp.modal('hide');
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

        $('#select-all-checkbox').on('click', function () {
            if (selectAllCheckbox.checked) {
                checkAllRows();
                selectedPageInfo.classList.remove('hide');
                const pageSize = document.querySelectorAll("#report_table_repeat_record_report tbody tr").length;
                document.getElementById("selected-page-count").innerText = pageSize;
                if (pageSize >= initialPageData.get('total')) {
                    selectTableButton.classList.add('hide');
                } else {
                    selectTableButton.classList.remove('hide');
                }
            } else {
                uncheckAllRows();
                selectedPageInfo.classList.add('hide');
                // just in case
                selectedTableInfo.classList.add('hide');
                selectedEntireTable = false;
            }
            updateActionButtons();
        });

        $('#report-content').on('click', '.record-checkbox', function () {
            resetTableSelections();
            updateActionButtons();
        });

        $('#report-content').on('click', '#report_table_repeat_record_report_length', function () {
            uncheckAllRows();
            resetTableSelections();
            updateActionButtons();
        });

        $('#report-content').on('click', '#report_table_repeat_record_report_paginate', function () {
            uncheckAllRows();
            resetTableSelections();
            updateActionButtons();
        });

        $("#select-table-button").click(function () {
            selectedEntireTable = true;
            selectedPageInfo.classList.add('hide');
            selectedTableInfo.classList.remove('hide');
            updateActionButtons();
        });

        $("#clear-table-selection").click(function () {
            uncheckAllRows();
            resetTableSelections();
            updateActionButtons();
        });

        $('body').on('DOMNodeInserted', 'tbody', function () {
            for (const item of items) {
                $(item).on('click', updateActionButtons);
            }
        });

        function performAction(action) {
            const checkedRecords = getCheckedRecords();
            if (selectedEntireTable) {
                hideAllWarnings();
                $popUp.modal('show');
            } else if (checkedRecords.length > 0) {
                if (isActionPossible(action)) {
                    hideAllWarnings();
                    $popUp.modal('show');
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

        function isActionPossible(action) {
            const containsQueuedRecords = selectionContainsQueuedRecords();
            if (containsQueuedRecords) {
                // all we can do is cancel
                return action === 'cancel'
            } else {
                // nothing is queued, so you shouldn't need to cancel
                return ['resend', 'requeue'].includes(action)
            }
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

        function checkAllRows() {
            for (const item of items) {
                if (item.type === 'checkbox') {
                    item.checked = true;
                }
            }
        }

        function uncheckAllRows() {
            for (const item of items) {
                if (item.type === 'checkbox') {
                    item.checked = false;
                }
            }
        }

        function updateActionButtons() {
            const checkedRecords = getCheckedRecords();
            if (checkedRecords.length === 0) {
                resendButton.disabled = true;
                requeueButton.disabled = true;
                cancelButton.disabled = true;
                return;
            }

            // default to no-op on cancelling a batch of records
            // that contain some already cancelled records
            // versus allowing no-op when queueing already queued
            // records
            if (selectionContainsQueuedRecords()) {
                resendButton.disabled = true;
                requeueButton.disabled = true;
                cancelButton.disabled = false;
            } else {
                resendButton.disabled = false;
                requeueButton.disabled = false;
                cancelButton.disabled = true;
            }
        }

        function selectionContainsQueuedRecords() {
            return getCheckedRecords().some(record => {
                return !!parseInt(record.getAttribute('is_queued'))
            });
        }

        function resetTableSelections() {
            selectedEntireTable = false;
            selectAllCheckbox.checked = false;
            selectedPageInfo.classList.add('hide');
            selectedTableInfo.classList.add('hide');
        }
    });
});
