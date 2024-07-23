"use strict";
/*
 * Handles communication about the status of SSO login after the inactivity
 * timer has requested a re-login
 */
hqDefine('hqwebapp/js/sso_inactivity', [], function () {
    localStorage.setItem('ssoInactivityMessage', JSON.stringify({
        isLoggedIn: true,
    }));
});
