hqDefine('email/js/email_settings', [
    "knockout",
    "jquery",
], function (ko, $) {

    function initFormBindings() {
        var viewModel = {
            isFormChanged: ko.observable(false),
            buttonText: ko.observable("Saved"),
        };

        $('form#email_settings_form :input').on('input', function () {
            viewModel.isFormChanged(true);
            viewModel.buttonText("Save");
        });

        ko.applyBindings(viewModel, document.getElementById("email_settings_form"));
    }

    $(document).ready(function () {
        initFormBindings();
    });
});
