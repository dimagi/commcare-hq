/*global FormplayerFrontend */

FormplayerFrontend.module("Utils", function (Utils, FormplayerFrontend, Backbone, Marionette) {
    Utils.Users = {
        /**
         * logInAsUser
         * :param: {String} restoreAsUsername - The username to restore as. Does not include
         *      `@<domain>.commcarehq.org` suffix
         * Logs a user in by setting the property on the current user and
         * setting it in a cookie
         */
        logInAsUser: function (restoreAsUsername) {
            var currentUser = FormplayerFrontend.request('currentUser');
            currentUser.restoreAs = restoreAsUsername;

            $.cookie(
                Utils.Users.restoreAsKey(
                    currentUser.domain,
                    currentUser.username
                ),
                currentUser.restoreAs
            );
        },
        restoreAsKey: function (domain, username) {
            return 'restoreAs:' + domain + ':' + username;
        },
        /**
         * getRestoreAsUser
         *
         * :param: {String} domain
         * :param: {String} username - username of the current user
         *
         * Returns the restore as user from the cookies or null if it doesn't exist
         */
        getRestoreAsUser: function (domain, username) {
            return $.cookie(Utils.Users.restoreAsKey(domain, username)) || null;
        },

        /**
         * clearRestoreAsUser
         *
         * :param: {String} domain
         * :param: {String} username - username of the current user
         *
         * Clears the restore as user from the cookies
         */
        clearRestoreAsUser: function (domain, username) {
            return $.removeCookie(Utils.Users.restoreAsKey(domain, username));
        },
    };
});
