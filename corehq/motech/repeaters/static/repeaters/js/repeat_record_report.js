/* globals CodeMirror */
hqDefine('domain/js/repeat_record_report', function() {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");

    $(function() {
        $('#report-content').on('click', '.toggle-next-attempt', function (e) {
            $(this).nextAll('.record-attempt').toggle();
            e.preventDefault();
        });
        var codeMirror = null;
        $('#view-record-payload-modal').on('shown.bs.modal', function(event) {
            var recordData = $(event.relatedTarget).data(),
                $modal = $(this);

            $.get({
                url: initialPageData.reverse("repeat_record"),
                data: { record_id: recordData.recordId },
                success: function(data) {
                    var $payload = $modal.find('.payload'),
                        contentType = data.content_type,
                        mode = 'xml';

                    if (contentType === 'text/xml') {
                        mode = 'xml';
                    } else if (contentType === 'application/json') {
                        mode = { name: 'javascript', json: true };
                    }

                    if (codeMirror === null) {
                        codeMirror = CodeMirror($payload[0], {
                            value: data.payload,
                            mode: mode,
                            readOnly: true,
                            lineNumbers: true,
                            lineWrapping: true,
                        });
                        codeMirror.refresh();
                    } else {
                        codeMirror.setValue(data.payload);
                    }
                },
                error: function(data) {
                    var defaultText = gettext('Failed to fetch payload'),
                        errorMessage = data.responseJSON ? data.responseJSON.error : null;

                    $modal.find('.modal-body').text(errorMessage || defaultText);
                },
            });
        });

        $('#view-record-payload-modal').on('hide.bs.modal', function() {
            if (codeMirror) {
                codeMirror.setValue('');
            }
        });

        $('#report-content').on('click', '.resend-record-payload', function() {
            var $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            $.post({
                url: initialPageData.reverse("repeat_record"),
                data: { record_id: recordId },
                success: function(data) {
                    $btn.removeSpinnerFromButton();
                    if (data.success) {
                        $btn.text(gettext('Success!'));
                        $btn.addClass('btn-success');
                    } else {
                        $btn.text(gettext('Failed'));
                        $btn.addClass('btn-danger');
                        $('#payload-error-modal').modal('show');
                        $('#payload-error-modal .error-message').text(data.failure_reason);
                    }
                },
                error: function() {
                    $btn.removeSpinnerFromButton();
                    $btn.text(gettext('Failed to send'));
                    $btn.addClass('btn-danger');
                },
            });
        });

        $('#report-content').on('click', '.cancel-record-payload', function() {
            var $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            $.post({
                url: initialPageData.reverse('cancel_repeat_record'),
                data: { record_id: recordId },
                success: function() {
                    $btn.removeSpinnerFromButton();
                    $btn.text(gettext('Success!'));
                    $btn.addClass('btn-success');
                },
                error: function() {
                    $btn.removeSpinnerFromButton();
                    $btn.text(gettext('Failed to cancel'));
                    $btn.addClass('btn-danger');
                },
            });
        });

        $('#report-content').on('click', '.requeue-record-payload', function() {
            var $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();

            $.post({
                url: initialPageData.reverse("requeue_repeat_record"),
                data: { record_id: recordId },
                success: function() {
                    $btn.removeSpinnerFromButton();
                    $btn.text(gettext('Success!'));
                    $btn.addClass('btn-success');
                },
                error: function() {
                    $btn.removeSpinnerFromButton();
                    $btn.text(gettext('Failed to cancel'));
                    $btn.addClass('btn-danger');
                },
            });
        });
    });
});
