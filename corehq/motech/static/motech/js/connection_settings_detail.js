hqDefine("motech/js/connection_settings_detail", [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    initialPageData
) {
    $(function () {
        var $testConnectionButton = $('#test-connection-button'),
            $testResult = $('#test-connection-result');

        /**
         * Handles a successful attempt to test the connection.
         *
         * Note: Just gets run when HQ returns success, not if the
         *       connection being tested returns success.
         */
        var handleSuccess = function (resp) {
            var message;
            $testResult.removeClass("hide text-danger text-success");
            $testConnectionButton.enableButton();

            if (resp.status) {
                message = resp.status + ": " + resp.response;
            } else {
                message = resp.response;
            }

            if (resp.success) {
                $testResult.addClass("text-success");
                $testResult.text(gettext('Success! Response is: ') + message);
            } else {
                $testResult.addClass("text-danger");
                $testResult.text(gettext('Failed! Response is: ') + message);
            }
        };

        var handleFailure = function (resp) {
            $testConnectionButton.enableButton();
            $testResult
                .removeClass("hide text-success")
                .addClass("text-danger");
            $testResult.text(gettext(
                'CommCare HQ was unable to make the request: '
            ) + resp.statusText);
        };

        $testConnectionButton.click(function () {
            var data = {
                name: $('#id_name').val(),
                url: $('#id_url').val(),
                auth_type: $('#id_auth_type').val(),
                username: $('#id_username').val(),
                plaintext_password: $('#id_plaintext_password').val(),
                skip_cert_verify: $('#id_skip_cert_verify').prop('checked'),
            };
            $testConnectionButton.disableButton();

            $.post({
                url: initialPageData.reverse("test_connection_settings"),
                data: data,
                success: handleSuccess,
                error: handleFailure,
            });
        });

        $('#id_url').change(function () {
            if ($(this).val()) {
                $testConnectionButton.removeClass('disabled');
            } else {
                $testConnectionButton.addClass('disabled');
            }
        });

        // Set initial button state
        $('#id_url').trigger('change');
    });
});
