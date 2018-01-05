/*global FormplayerFrontend, Util */

/**
 * Backbone model for listing and selecting FormEntrySessions
 */

FormplayerFrontend.module("Sessions", function (Sessions, FormplayerFrontend, Backbone, Marionette, $) {

    Sessions.API = {

        getSessions: function () {

            var user = FormplayerFrontend.request('currentUser');
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
                    if (response.hasOwnProperty('exception')){
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

            var menus = new Sessions.Collections.FormEntrySession(options);

            var defer = $.Deferred();
            menus.fetch(options);
            return defer.promise();
        },

        getSession: function (sessionId) {

            var user = FormplayerFrontend.request('currentUser');
            var formplayerUrl = user.formplayer_url;
            var menus = new FormplayerFrontend.Menus.Collections.MenuSelect();
            var defer = $.Deferred();

            menus.fetch({
                data: JSON.stringify({
                    "sessionId": sessionId,
                    "username": user.username,
                    "domain": user.domain,
                    "restoreAs": user.restoreAs,
                    "tz_offset_millis": FormplayerFrontend.request('timezoneOffset'),
                }),
                url: formplayerUrl + '/incomplete-form',
                success: function (request) {
                    defer.resolve(request);
                },
            });
            return defer.promise();
        },

        deleteSession: function(session) {
            var user = FormplayerFrontend.request('currentUser');
            var options = {
                data: JSON.stringify({
                    "sessionId": session.get('sessionId'),
                    "username": user.username,
                    "domain": user.domain,
                    "restoreAs": user.restoreAs,
                }),
                url: user.formplayer_url + '/delete-incomplete-form',
                complete: function(xhr) {
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

    FormplayerFrontend.reqres.setHandler("getSession", function (session) {
        return Sessions.API.getSession(session);
    });

    FormplayerFrontend.reqres.setHandler("deleteSession", function (sessionId) {
        return Sessions.API.deleteSession(sessionId);
    });

    FormplayerFrontend.reqres.setHandler("sessions", function () {
        return Sessions.API.getSessions();
    });
});

