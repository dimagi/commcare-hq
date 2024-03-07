'use strict';
/* global Sentry */
hqDefine("cloudcare/js/formplayer/users/utils", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        initialPageData = hqImport("hqwebapp/js/initial_page_data");

    var self = {};
    self.Users = {
        /**
         * logInAsUser
         * :param: {String} restoreAsUsername - The username to restore as. Does not include
         *      `@<domain>.commcarehq.org` suffix
         * Logs a user in by setting the property on the current user and
         * setting it in a cookie
         */
        logInAsUser: function (restoreAsUsername) {
            var currentUser = FormplayerFrontend.getChannel().request('currentUser');
            currentUser.restoreAs = restoreAsUsername;
            Sentry.setTag("loginAsUser", restoreAsUsername);

            $.cookie(
                self.Users.restoreAsKey(
                    currentUser.domain,
                    currentUser.username
                ),
                currentUser.restoreAs,
                { secure: initialPageData.get('secure_cookies') }
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
            return $.cookie(self.Users.restoreAsKey(domain, username)) || null;
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
            Sentry.setTag("loginAsUser", null);
            return $.removeCookie(self.Users.restoreAsKey(domain, username));
        },
    };

    FormplayerFrontend.getChannel().reply('restoreAsUser', function (domain, username) {
        return self.Users.getRestoreAsUser(
            domain,
            username
        );
    });

    /**
     * clearRestoreAsUser
     *
     * This will unset the localStorage restore as user as well as
     * unset the restore as user from the currentUser. It then
     * navigates you to the main page.
     */
    FormplayerFrontend.on('clearRestoreAsUser', function () {
        var user = FormplayerFrontend.getChannel().request('currentUser');
        self.Users.clearRestoreAsUser(
            user.domain,
            user.username
        );
        user.restoreAs = null;
        hqRequire(["cloudcare/js/formplayer/users/views"], function (UsersViews) {
            FormplayerFrontend.regions.getRegion('restoreAsBanner').show(
                UsersViews.RestoreAsBanner({
                    model: user,
                })
            );
        });

        FormplayerFrontend.trigger('navigateHome');
    });

    return self;
});
