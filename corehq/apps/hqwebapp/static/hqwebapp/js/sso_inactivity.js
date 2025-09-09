/*
 * Handles communication about the status of SSO login after the inactivity
 * timer has requested a re-login
 */
import "commcarehq";

localStorage.setItem('ssoInactivityMessage', JSON.stringify({
    isLoggedIn: true,
}));
