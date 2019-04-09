hqDefine("repeaters/js/add_form_repeater", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/widgets',       // case repeaters ("Forward Cases") use .hqwebapp-select2
    'locations/js/widgets',         // openmrs repeaters use the LocationSelectWidget
], function (
    $,
    initialPageData
) {
    $(function () {
        var $testLinkButton = $('#test-forward-link'),
            $testResult = $('#test-forward-result');

        var handleSuccess = function (resp) {
            /*
             * Handles a successful attempt to test the link. Note, just gets run when HQ returns
             * successful not if the link being tested returns successful
             */
            var jsonResp = JSON.parse(resp),
                message;
            $testResult.removeClass("hide text-danger text-success");
            $testLinkButton.enableButton();

            if (jsonResp.status) {
                message = jsonResp.status + ": " + jsonResp.response;
            } else {
                message = jsonResp.response;
            }

            if (jsonResp.success) {
                $testResult.addClass("text-success");
                $testResult.text(gettext('Success! Response is: ') + message);
            } else {
                $testResult.addClass("text-danger");
                $testResult.text(gettext('Failed! Response is: ') + message);
            }
        };

        var handleFailure = function (resp) {
            /*
             * Handles an HQ failure to test the URL
             */
            $testLinkButton.enableButton();
            $testResult
                .removeClass("hide text-success")
                .addClass("text-danger");
            $testResult.text(gettext('HQ was unable to make the request: ') + resp.statusText);
        };

        $testLinkButton.click(function () {
            var data = {
                url: $('#id_url').val(),
                format: $('#id_format').val(),
                repeater_type: initialPageData.get("repeater_type"),
                auth_type: $('#id_auth_type').val(),
                username: $('#id_username').val(),
                password: $('#id_password').val(),
                skip_cert_verify: $('#id_skip_cert_verify').prop('checked'),
            };
            $testLinkButton.disableButton();

            $.post({
                url: initialPageData.reverse("test_repeater"),
                data: data,
                success: handleSuccess,
                error: handleFailure,
            });
        });

        $('#id_url').change(function () {
            if ($(this).val()) {
                $testLinkButton.removeClass('disabled');
            } else {
                $testLinkButton.addClass('disabled');
            }
        });

        // Set initial button state
        $('#id_url').trigger('change');
    });
});
