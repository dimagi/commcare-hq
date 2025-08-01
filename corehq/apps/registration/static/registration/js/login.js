import "commcarehq";
import $ from "jquery";
import userLoginForm from "registration/js/user_login_form";
import initialPageData from "hqwebapp/js/initial_page_data";
import serverLocationSelect from "registration/js/server_location_select";
import "hqwebapp/js/captcha";  // shows captcha
import "select2/dist/js/select2.full.min";

$(function () {

    // populate username field if set in the query string
    const urlParams = new URLSearchParams(window.location.search);
    const isSessionExpiration = initialPageData.get('is_session_expiration');

    let username = urlParams.get('username');
    const usernameElt = document.getElementById('id_auth-username');
    if (username && usernameElt) {
        if (isSessionExpiration && username.endsWith("commcarehq.org")) {
            username = username.split("@")[0];
        }
        usernameElt.value = username;
        if (isSessionExpiration) {
            usernameElt.readOnly = true;
        }
    }

    const enforceSsoLogin = initialPageData.get('enforce_sso_login');
    const canSelectServer = initialPageData.get('can_select_server');

    let loginFormModel = {};
    if (enforceSsoLogin) {
        const $passwordField = $('#id_auth-password');
        loginFormModel = userLoginForm.loginController({
            initialUsername: $('#id_auth-username').val(),
            passwordField: $passwordField,
            passwordFormGroup: $passwordField.closest('.form-group'),
            nextUrl: urlParams.get('next'),
            isSessionExpiration: isSessionExpiration,
        });
    }

    const serverLocationEl = '#id_auth-server_location';
    if (canSelectServer) {
        const serverLocationModel = serverLocationSelect({
            initialValue: $(serverLocationEl).val(),
        });
        loginFormModel.serverLocation = serverLocationModel.serverLocation;
    }

    if (enforceSsoLogin || canSelectServer) {
        const $bindingEl = enforceSsoLogin ? $('#user-login-form') : $(serverLocationEl);
        $bindingEl.koApplyBindings(loginFormModel);
        if (enforceSsoLogin) {
            loginFormModel.init();
        }
        if (canSelectServer) {
            $(serverLocationEl).select2({disabled: false, minimumResultsForSearch: Infinity});
        }
    }
});
