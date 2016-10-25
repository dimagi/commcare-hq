/*global FormplayerFrontend, Util */

FormplayerFrontend.module("Utils", function(Utils, FormplayerFrontend, Backbone, Marionette){
    Utils.Users = {
        /**
         * logInAsUser
         * :param: {String} restoreAsUsername - The username to restore as. Does not include
         *      `@<domain>.commcarehq.org` suffix
         * Logs a user in by setting the property on the current user and
         * setting it in localStorage
         */
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
        /**
         * getRestoreAsUser
         *
         * :param: {String} domain
         * :param: {String} username - username of the current user
         *
         * Returns the restore as user from localstorage
         */
        getRestoreAsUser: function(domain, username) {
            return window.localStorage.getItem(
                Utils.Users.restoreAsKey(domain, username)
            );
        },

        /**
         * clearRestoreAsUser
         *
         * :param: {String} domain
         * :param: {String} username - username of the current user
         *
         * Clears the restore as user from localstorage with an empty string
         */
        clearRestoreAsUser: function(domain, username) {
            return window.localStorage.setItem(
                Utils.Users.restoreAsKey(domain, username),
                ''
            );
        },
    };
});
