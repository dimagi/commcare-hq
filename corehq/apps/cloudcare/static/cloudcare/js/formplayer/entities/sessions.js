/*global FormplayerFrontend, Util */

/**
 * Backbone model for listing and selecting FormEntrySessions
 * TODO Shares too much logic with menu.js which should be refactored
 */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {

    Entities.FormEntrySession = Backbone.Model.extend({
        isNew: function() {
            return !this.get('sessionId');
        },
        sync: function (method, model, options) {
            Util.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });

    Entities.FormEntrySessionCollection = Backbone.Collection.extend({

        model: Entities.FormEntrySession,

        parse: function (response) {
            return response.sessions;
        },

        fetch: function (options) {
            Util.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.fetch.call(this, options);
        },
    });

    var API = {

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
                success: function (request) {
                    defer.resolve(request);
                },
            };

            var menus = new Entities.FormEntrySessionCollection(options);

            var defer = $.Deferred();
            menus.fetch(options);
            return defer.promise();
        },

        getSession: function (sessionId) {

            var user = FormplayerFrontend.request('currentUser');
            var formplayerUrl = user.formplayer_url;

            var menus = new Entities.MenuSelectCollection({

                fetch: function (options) {

                    options.data = JSON.stringify({
                        "sessionId": sessionId,
                        "username": user.username,
                        "domain": user.domain,
                        "restoreAs": user.restoreAs,
                    });

                    options.url = formplayerUrl + '/incomplete-form';
                    Util.setCrossDomainAjaxOptions(options);
                    return Backbone.Collection.prototype.fetch.call(this, options);
                },

                initialize: function (params) {
                    this.fetch = params.fetch;
                },

            });

            var defer = $.Deferred();
            menus.fetch({
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
                        console.error(xhr.responseJSON.exception);
                    }

                },
            };

            session.destroy(options);
        },
    };

    FormplayerFrontend.reqres.setHandler("getSession", function (session) {
        return API.getSession(session);
    });

    FormplayerFrontend.reqres.setHandler("deleteSession", function (sessionId) {
        return API.deleteSession(sessionId);
    });

    FormplayerFrontend.reqres.setHandler("sessions", function () {
        return API.getSessions();
    });
});
