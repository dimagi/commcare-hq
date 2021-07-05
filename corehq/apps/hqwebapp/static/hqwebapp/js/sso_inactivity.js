/*
 * Handles communication about the status of SSO login after the inactivity
 * timer has requested a re-login
 */
hqDefine('hqwebapp/js/sso_inactivity', [
    'jquery',
], function (
    $,
) {

    console.log('loaded sso inactivity!');
    localStorage.setItem('ssoInactivityMessage', JSON.stringify({
        isLoggedIn: true,
    }));
    console.log('set ssoInactivityMessage');

});
