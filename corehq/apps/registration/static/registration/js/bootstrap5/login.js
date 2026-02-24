import "commcarehq";
import $ from "jquery";
import userLoginForm from "registration/js/bootstrap5/user_login_form";
import initialPageData from "hqwebapp/js/initial_page_data";
import "hqwebapp/js/captcha";  // shows captcha

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
        var loginController = userLoginForm.loginController({
            initialUsername: $('#id_auth-username').val(),
            passwordField: $('#id_auth-password'),
            passwordFormGroupId: 'form-group-password',
            nextUrl: urlParams.get('next'),
            isSessionExpiration: isSessionExpiration,
        });
        $('#user-login-form').koApplyBindings(loginController);
        loginController.init();
    }
});

