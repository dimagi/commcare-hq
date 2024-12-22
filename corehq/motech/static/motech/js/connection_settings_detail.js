'use strict';
hqDefine("motech/js/connection_settings_detail", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'commcarehq',
], function (
    $,
    _,
    initialPageData
) {
    $(function () {
        var $authTypeSelect = $('#id_auth_type'),
            $testConnectionButton = $('#test-connection-button'),
            $authPreset = $("#id_auth_preset"),
            $testResult = $('#test-connection-result');

        $authPreset.change(function () {
            var authPreset = $(this).val(),
                customAuthPresetFields = [
                    'token_url',
                    'refresh_url',
                    'pass_credentials_in_header',
                    'include_client_id',
                    'scope',
                ];
            if (authPreset === 'CUSTOM') {
                _.each(customAuthPresetFields, function (field) {
                    $('#div_id_' + field).removeClass("d-none");
                });
            } else {
                _.each(customAuthPresetFields, function (field) {
                    $('#div_id_' + field).addClass("d-none");
                });
            }

        });

        $authTypeSelect.change(function (e, fromInitial) {
            let visible = {},
                allFields = {
                    'username': gettext("Username"),
                    'plaintext_password': gettext("Password"),
                    'client_id': gettext("Client ID"),
                    'plaintext_client_secret': gettext("Client Secret"),
                    'oauth_settings': null,
                },
                placeholders = {
                };
            switch ($(this).val()) {
                case '':  // Auth type is "None"
                    break;
                case 'oauth1':
                    visible = {
                        'username': null,
                        'plaintext_password': null,
                    };
                    break;
                case 'oauth2_pwd':
                    visible = allFields;
                    break;
                case 'oauth2_client':
                    visible = {
                        'client_id': null,
                        'plaintext_client_secret': null,
                        'oauth_settings': null,
                    };
                    break;
                case 'api_key':
                    visible = {
                        'username': gettext("HTTP Header Name"),
                        'plaintext_password': gettext("API Key"),
                    };
                    placeholders['username'] = 'Authorization';
                    break;
                default:
                    visible = {
                        'username': null,
                        'plaintext_password': null,
                    };
            }
            _.each(_.keys(allFields), function (field) {
                let div = $('#div_id_' + field);
                if (field in visible) {
                    div.removeClass("d-none");
                    let label = visible[field] || allFields[field];
                    let labelElement = div.find('label');
                    if (!fromInitial && label && labelElement.length > 0 && labelElement.text() !== label) {
                        labelElement.text(label);
                        let fieldElement = $('#id_' + field);
                        fieldElement.val('');  // clear current value
                        fieldElement.attr('placeholder', placeholders[field] || '');
                    }
                } else {
                    div.addClass("d-none");
                }
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
            $testResult.removeClass("d-none text-danger text-success");
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
                .removeClass("d-none text-success")
                .addClass("text-danger");
            $testResult.text(gettext(
                'CommCare HQ was unable to make the request: '
            ) + resp.statusText);
        };

        $testConnectionButton.click(function () {
            var data = {
                name: $('#id_name').val(),
                notify_addresses_str: $('#id_notify_addresses_str').val(),
                url: $('#id_url').val(),
                auth_type: $('#id_auth_type').val(),
                api_auth_settings: $('#id_api_auth_settings').val(),
                username: $('#id_username').val(),
                plaintext_password: $('#id_plaintext_password').val(),
                client_id: $('#id_client_id').val(),
                plaintext_client_secret: $('#id_plaintext_client_secret').val(),
                pass_credentials_in_header: $('#id_pass_credentials_in_header').prop('checked'),
                include_client_id: $('#id_include_client_id').prop('checked'),
                scope: $('#id_scope').val(),
                token_url: $('#id_token_url').val(),
                auth_preset: $('#id_auth_preset').val(),
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
        $authTypeSelect.trigger('change', [true]);
        $authPreset.trigger('change');
        $('#id_url').trigger('change');
    });
});
