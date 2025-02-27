hqDefine("case/js/repeat_records", [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    initialPageData,
) {
    $(function () {
        $('.requeue-record-payload').click(function () {
            var $btn = $(this),
                recordId = $btn.data().recordId;
            $btn.disableButton();
            $.post({
                url: initialPageData.reverse('requeue_repeat_record'), // this url is added to the page in case_details.html
                data: { record_id: recordId },
                success: function () {
                    $btn.removeSpinnerFromButton();
                    $btn.text(gettext('Requeued'));
                    $btn.addClass('btn-success');
                },
                error: function () {
                    $btn.removeSpinnerFromButton();
                    $btn.text(gettext('Failed'));
                    $btn.addClass('btn-danger');
                },
            });
        });
    });
});
