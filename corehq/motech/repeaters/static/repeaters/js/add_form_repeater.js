$(function() {
    var $testLinkButton = $('#test-forward-link'),
        $testResult = $('#test-forward-result');

    var handleSuccess = function(resp) {
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

    var handleFailure = function(resp) {
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
            repeater_type: hqImport("hqwebapp/js/initial_page_data").get("repeater_type"),
            auth_type: $('#id_auth_type').val(),
            username: $('#id_username').val(),
            password: $('#id_password').val(),
        };
        $testLinkButton.disableButton();

        $.post({
            url: hqImport("hqwebapp/js/initial_page_data").reverse("test_repeater"),
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
});
