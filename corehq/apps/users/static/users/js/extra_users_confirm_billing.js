hqDefine("users/js/extra_users_confirm_billing", function() {
    $(function () {
        // Only allow saving once agreement is confirmed
        $('#id_confirm_product_agreement').click(function () {
            var $submit = $('#submit-button-pa'),
                $helpText = $('#submit-button-help-qa');
            if ($(this).prop('checked')) {
                $submit.prop('disabled', false);
                $submit.removeClass('disabled');
                $helpText.addClass('hide');
            } else {
                $submit.prop('disabled', true);
                $submit.addClass('disabled');
                $helpText.removeClass('hide');
            }
        });
    });
});
