hqDefine("motech/js/connection_settings_detail", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    initialPageData
) {
    $(function () {
        var $authTypeSelect = $('#id_auth_type'),
            $testConnectionButton = $('#test-connection-button'),
            $testResult = $('#test-connection-result');

        $authTypeSelect.change(function () {
            var visible = [],
                hidden = [],
                allFields = [
                    'api_auth_settings',
                    'username',
                    'plaintext_password',
                    'client_id',
                    'plaintext_client_secret',
                ];
            switch ($(this).val()) {
                case '':  // Auth type is "None"
                    hidden = allFields;
                    break;
                case 'oauth1':
                    visible = [
                        'api_auth_settings',
                        'username',
                        'plaintext_password',
                    ];
                    hidden = [
                        'client_id',
                        'plaintext_client_secret',
                    ];
                    break;
                case 'oauth2_pwd':
                    visible = allFields;
                    break;
                default:
                    visible = [
                        'username',
                        'plaintext_password',
                    ];
                    hidden = [
                        'api_auth_settings',
                        'client_id',
                        'plaintext_client_secret',
                    ];
            }
            _.each(visible, function (field) {
                $('#div_id_' + field).show();
            });
            _.each(hidden, function (field) {
                $('#div_id_' + field).hide();
            });
        });

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

        // Set initial state
        $authTypeSelect.trigger('change');
        $('#id_url').trigger('change');
    });
});
