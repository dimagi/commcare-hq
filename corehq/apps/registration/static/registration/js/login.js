import "commcarehq";
import $ from "jquery";
import userLoginForm from "registration/js/user_login_form";
import initialPageData from "hqwebapp/js/initial_page_data";
import serverLocationSelect from "registration/js/server_location_select";
import "hqwebapp/js/captcha";  // shows captcha
import "select2/dist/js/select2.full.min";

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

    if (initialPageData.get('can_select_server')) {
        var $serverLocationField = $('#id_auth-server_location');
        var serverLocationModel = serverLocationSelect.serverLocationModel({
            initialValue: $serverLocationField.val(),
        });
        $serverLocationField.koApplyBindings(serverLocationModel);
        $serverLocationField.select2({disabled: false, minimumResultsForSearch: Infinity});
    }
});
