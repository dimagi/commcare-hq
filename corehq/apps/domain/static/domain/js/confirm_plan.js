hqDefine("domain/js/confirm_plan", function () {
    var checked = "checked",
        disabled = "disabled",
        hide = "hide";

    $(function () {
        $('#confirm-eula').click(function () {
            var $submit = $('#submit-button-pa'),
                $helpText = $('#submit-button-help-qa');
            if ($(this).prop(checked)) {
                $submit.prop(disabled, false);
                $submit.removeClass(disabled);
                $helpText.addClass(hide);
            } else {
                $submit.prop(disabled, true);
                $submit.addClass(disabled);
                $helpText.removeClass(hide);
            }
        });
    });
});
