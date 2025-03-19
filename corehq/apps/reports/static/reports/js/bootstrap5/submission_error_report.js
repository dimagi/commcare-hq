hqDefine("reports/js/bootstrap5/submission_error_report", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'reports/js/bootstrap5/base',
    'commcarehq',
], function (
    $,
    initialPageData,
) {
    $(function () {
        $('#report-content').on('click', '.reprocess-error', function () {
            var $btn = $(this),
                formId = $btn.data().formId;
            $btn.disableButton();

            $.post({
                url: initialPageData.reverse('reprocess_xform_errors'),
                data: { form_id: formId },
                success: function (data) {
                    $btn.removeSpinnerFromButton();
                    if (data.success) {
                        $btn.text(gettext('Success!'));
                        $btn.addClass('btn-success');
                    } else {
                        $btn.text(gettext('Failed'));
                        $btn.addClass('btn-danger');
                        $('#processing-error-modal').modal('show');  /* todo B5: plugin:modal */
                        $('#processing-error-modal .error-message').text(data.failure_reason);
                    }
                },
                error: function () {
                    $btn.removeSpinnerFromButton();
                    $btn.text(gettext('Failed to re-process'));
                    $btn.addClass('btn-danger');
                },
            });
        });
    });
});
