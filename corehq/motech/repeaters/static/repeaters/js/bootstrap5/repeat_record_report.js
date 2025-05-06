import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import ace from "ace-builds/src-min-noconflict/ace";
import "ace-builds/src-min-noconflict/mode-json";
import "ace-builds/src-min-noconflict/mode-xml";
import "reports/js/bootstrap5/base";
import "reports/js/bootstrap5/tabular";

const selectAllCheckbox = document.getElementById('select-all-checkbox'),
    selectedPageInfo = document.getElementById('selected-page-info'),
    selectedTableInfo = document.getElementById('selected-table-info'),
    selectTableButton = document.getElementById('select-table-button'),
    items = document.getElementsByName('record_ids'),
    cancelButton = document.getElementById('cancel-button'),
    requeueButton = document.getElementById('requeue-button'),
    resendButton = document.getElementById('resend-button'),
    $popUp = $('#are-you-sure'),
    $confirmButton = $('#confirm-button'),
    payloadId = initialPageData.get('payload_id'),
    repeaterId = initialPageData.get('repeater_id');

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
        $popUp.modal('show');  /* todo B5: plugin:modal */
    });

    $('#cancel-button').on('click', function () {
        setAction('cancel');
        $popUp.modal('show');  /* todo B5: plugin:modal */
    });

    $('#requeue-button').on('click', function () {
        setAction('requeue');
        $popUp.modal('show');  /* todo B5: plugin:modal */
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

    $('#select-all-checkbox').on('click', function () {
        if (selectAllCheckbox.checked) {
            checkAllRows();
            selectedPageInfo.classList.remove('d-none');
            const pageSize = document.querySelectorAll("#report_table_repeat_record_report tbody tr").length;
            document.getElementById("selected-page-count").innerText = pageSize;
            if (pageSize >= initialPageData.get('total')) {
                selectTableButton.classList.add('d-none');
            } else {
                selectTableButton.classList.remove('d-none');
            }
        } else {
            uncheckAllRows();
            selectedPageInfo.classList.add('d-none');
            // just in case
            selectedTableInfo.classList.add('d-none');
            selectedEntireTable = false;
        }
        updateActionButtons();
    });

    $('#report-content').on('click', '.record-checkbox', function () {
        resetTableSelections();
        updateActionButtons();
    });

    $('#report-content').on('click', '#report_table_repeat_record_report_length', function () {
        resetPage();
    });

    $('#report-content').on('click', '#report_table_repeat_record_report_paginate', function () {
        resetPage();
    });

    $("#select-table-button").click(function () {
        selectedEntireTable = true;
        selectedPageInfo.classList.add('d-none');
        selectedTableInfo.classList.remove('d-none');
        updateActionButtons();
    });

    $("#clear-table-selection").click(function () {
        resetPage();
    });

    $('body').on('DOMNodeInserted', 'tbody', function () {
        for (const item of items) {
            $(item).on('click', updateActionButtons);
        }
    });

    function getCheckedRecords() {
        return $.find('input[type=checkbox][name=record_ids]:checked');
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
            payload_id: payloadId,
            repeater_id: repeaterId,
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
                resetPage();
            },
            error: function () {
                btn.removeSpinnerFromButton();
                btn.text(gettext('Failed to send'));
                btn.addClass('btn-danger');
                resetPage();
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
                resetPage();
            },
            error: function () {
                btn.removeSpinnerFromButton();
                btn.text(gettext('Failed to cancel'));
                btn.addClass('btn-danger');
                resetPage();
            },
        });
    }

    function setAction(action) {
        $confirmButton.attr('data-action', action);
    }

    function getAction() {
        return $confirmButton.attr('data-action');
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
        const disallowBulkAction = payloadId === "" && repeaterId === "" && selectedEntireTable;
        const checkedRecords = getCheckedRecords();
        if (checkedRecords.length === 0 || disallowBulkAction) {
            resendButton.disabled = true;
            requeueButton.disabled = true;
            cancelButton.disabled = true;
            return;
        }

        // resending is always an option
        resendButton.disabled = false;
        // default to no-op on cancelling a batch of records
        // that contain some already cancelled records
        // versus allowing no-op when queueing already queued
        // records
        if (selectionContainsQueuedRecords()) {
            requeueButton.disabled = true;
            cancelButton.disabled = false;
        } else {
            requeueButton.disabled = false;
            cancelButton.disabled = true;
        }
    }

    function selectionContainsQueuedRecords() {
        return getCheckedRecords().some(record => {
            return !!parseInt(record.getAttribute('is_queued'));
        });
    }

    function resetTableSelections() {
        selectedEntireTable = false;
        selectAllCheckbox.checked = false;
        selectedPageInfo.classList.add('d-none');
        selectedTableInfo.classList.add('d-none');
    }

    function resetPage() {
        uncheckAllRows();
        resetTableSelections();
        updateActionButtons();
    }
});
