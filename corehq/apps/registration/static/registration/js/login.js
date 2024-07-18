hqDefine('registration/js/login', [
    'jquery',
    'analytix/js/kissmetrix',
    'registration/js/user_login_form',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/captcha', // shows captcha
], function (
    $,
    kissmetrics,
    userLoginForm,
    initialPageData
) {
    $(function () {

        // populate username field if set in the query string
        var urlParams = new URLSearchParams(window.location.search);
        var isSessionExpiration = initialPageData.get('is_session_expiration');

        var username = urlParams.get('username');
        var usernameElt = document.getElementById('id_auth-username');
        if (username && usernameElt) {
            if (isSessionExpiration && username.endsWith("commcarehq.org")) {
                username = username.split("@")[0];
            }
            usernameElt.value = username;
            if (isSessionExpiration) {
                usernameElt.readOnly = true;
            }
        }

        if (initialPageData.get('enforce_sso_login')) {
            var $passwordField = $('#id_auth-password');
            var loginController = userLoginForm.loginController({
                initialUsername: $('#id_auth-username').val(),
                passwordField: $passwordField,
                passwordFormGroup: $passwordField.closest('.form-group'),
                nextUrl: urlParams.get('next'),
                isSessionExpiration: isSessionExpiration,
            });
            $('#user-login-form').koApplyBindings(loginController);
            loginController.init();
        }

        kissmetrics.whenReadyAlways(function () {

            $('#cta-form-get-demo-button-body').click(function () {
                kissmetrics.track.event("Demo Workflow - Body Button Clicked");
            });

            $('#cta-form-get-demo-button-header').click(function () {
                kissmetrics.track.event("Demo Workflow - Header Button Clicked");
            });
        });
    });

});
