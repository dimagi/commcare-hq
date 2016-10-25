/*global FormplayerFrontend */

FormplayerFrontend.module("Utils", function(Utils, FormplayerFrontend, Backbone, Marionette, $){
    Utils.Users = {
        logInAsUser: function(restoreAsUsername) {
            var currentUser = FormplayerFrontend.request('currentUser');
            currentUser.restoreAs = restoreAsUsername;
            window.localStorage.setItem(
                Utils.Users.restoreAsKey(
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
                Utils.Users.restoreAsKey(domain, username)
            );
        },
        clearRestoreAsUser: function() {
            return window.localStorage.setItem(
                Utils.Users.restoreAsKey(domain, username),
                ''
            );
        },
    }
});
