/*global FormplayerFrontend, Util */

/**
 * Backbone model for listing and selecting FormEntrySessions
 */

hqDefine("cloudcare/js/formplayer/sessions/api", function () {

    var API = {

        getSessions: function () {

            var user = FormplayerFrontend.getChannel().request('currentUser');
            var domain = user.domain;
            var formplayerUrl = user.formplayer_url;
            var options = {
                parse: true,
                data: JSON.stringify({
                    "username": user.username,
                    "domain": domain,
                    "restoreAs": user.restoreAs,
                }),
                url: formplayerUrl + '/get_sessions',
                success: function (parsed, response) {
                    if (response.hasOwnProperty('exception')) {
                        FormplayerFrontend.trigger(
                            'showError',
                            response.exception || FormplayerFrontend.Constants.GENERIC_ERROR,
                            response.type === 'html'
                        );
                        FormplayerFrontend.trigger('navigation:back');
                    } else {
                        defer.resolve(parsed);
                    }
                },
            };

            var menus = hqImport("cloudcare/js/formplayer/sessions/collections")(options);

            var defer = $.Deferred();
            menus.fetch(options);
            return defer.promise();
        },

        getSession: function (sessionId) {

            var user = FormplayerFrontend.getChannel().request('currentUser');
            var formplayerUrl = user.formplayer_url;
            var menus = hqImport("cloudcare/js/formplayer/menus/collections")();
            var defer = $.Deferred();

            menus.fetch({
                data: JSON.stringify({
                    "sessionId": sessionId,
                    "username": user.username,
                    "domain": user.domain,
                    "restoreAs": user.restoreAs,
                    "tz_offset_millis": (new Date()).getTimezoneOffset() * 60 * 1000 * -1,
                }),
                url: formplayerUrl + '/incomplete-form',
                success: function (request) {
                    defer.resolve(request);
                },
            });
            return defer.promise();
        },

        deleteSession: function (session) {
            var user = FormplayerFrontend.getChannel().request('currentUser');
            var options = {
                data: JSON.stringify({
                    "sessionId": session.get('sessionId'),
                    "username": user.username,
                    "domain": user.domain,
                    "restoreAs": user.restoreAs,
                }),
                url: user.formplayer_url + '/delete-incomplete-form',
                complete: function (xhr) {
                    if (xhr.responseJSON.status === 'error') {
                        FormplayerFrontend.trigger(
                            'showError',
                            "Unable to delete incomplete form '" + session.get('title') + "'"
                        );
                        window.console.error(xhr.responseJSON.exception);
                    }

                },
            };

            session.destroy(options);
        },
    };

    FormplayerFrontend.getChannel().reply("getSession", function (session) {
        return API.getSession(session);
    });

    FormplayerFrontend.getChannel().reply("deleteSession", function (sessionId) {
        return API.deleteSession(sessionId);
    });

    FormplayerFrontend.getChannel().reply("sessions", function () {
        return API.getSessions();
    });

    return API;
});

