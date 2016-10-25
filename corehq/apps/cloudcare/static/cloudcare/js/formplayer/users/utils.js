/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.Users", function(Users, FormplayerFrontend, Backbone, Marionette, $){
    Users.Utils = {
        logInAsUser: function(restoreAsUsername) {
            var currentUser = FormplayerFrontend.request('currentUser');
            currentUser.restoreAs = restoreAsUsername;
            window.localStorage.setItem(
                Users.Utils.restoreAsKey(
                    currentUser.domain,
                    currentUser.username
                ),
                currentUser.restoreAs
            );
        },
        restoreAsKey: function(domain, username) {
            return domain + ':' + username;
        },
        getRestoreAsUser: function(domain, username) {
            return window.localStorage.getItem(
                Users.Utils.restoreAsKey(domain, username)
            );
        }
    }
});
