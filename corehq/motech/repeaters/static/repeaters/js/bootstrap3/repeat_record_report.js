hqDefine('repeaters/js/bootstrap3/repeat_record_report', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'ace-builds/src-min-noconflict/ace',
    'ace-builds/src-min-noconflict/mode-json',
    'ace-builds/src-min-noconflict/mode-xml',
    'repeaters/js/repeat_record_report_selects',
    'reports/js/bootstrap3/base',
    'reports/js/bootstrap3/tabular',
    'commcarehq',
], function (
    $,
    initialPageData,
    ace,
) {
    const selectAll = document.getElementById('select-all'),
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

        function performAction(action) {
            const checkedRecords = getCheckedRecords();
            if (selectAll.checked) {
                hideAllWarnings();
                $popUp.modal('show');
            } else if (checkedRecords.length > 0) {
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

        function getCheckedRecords() {
            return $.find('input[type=checkbox][name=record_ids]:checked');
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
            if (selectAll.checked) {
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
    });
});
