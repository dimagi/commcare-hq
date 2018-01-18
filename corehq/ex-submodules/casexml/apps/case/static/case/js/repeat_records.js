$(function(){
    $('.requeue-record-payload').click(function() {
        var $btn = $(this),
            recordId = $btn.data().recordId,
            reverse = hqImport('hqwebapp/js/initial_page_data').reverse;
        $btn.disableButton();
        $.post({
            url: reverse('requeue_repeat_record'), // this url is added to the page in case_details.html
            data: { record_id: recordId },
            success: function() {
                $btn.removeSpinnerFromButton();
                $btn.text(gettext('Requeued'));
                $btn.addClass('btn-success');
            },
            error: function() {
                $btn.removeSpinnerFromButton();
                $btn.text(gettext('Failed'));
                $btn.addClass('btn-danger');
            },
        });
    });
});
