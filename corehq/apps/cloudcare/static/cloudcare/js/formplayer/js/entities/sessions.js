/*global FormplayerFrontend */

/**
 * Backbone model for listing and selecting FormEntrySessions
 * TODO Shares too much logic with menu.js which should be refactored
 */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {

    Entities.FormEntrySession = Backbone.Model.extend({});

    Entities.FormEntrySessionCollection = Backbone.Collection.extend({

        model: Entities.FormEntrySession,

        parse: function (response) {
            return response.sessions;
        },

        initialize: function (params) {
            this.fetch = params.fetch;
        },
    });

    var API = {

        getSessions: function () {

            var user = FormplayerFrontend.request('currentUser');
            var username = user.username;
            var domain = user.domain;
            var formplayerUrl = user.formplayer_url;
            var trimmedUsername = username.substring(0, username.indexOf("@"));

            var menus = new Entities.FormEntrySessionCollection({

                fetch: function (options) {

                    options.data = JSON.stringify({
                        "username": trimmedUsername,
                        "domain": domain,
                    });

                    options.url = formplayerUrl + '/get_sessions';
                    options.type = 'POST';
                    options.dataType = "json";
                    options.crossDomain = {crossDomain: true};
                    options.xhrFields = {withCredentials: true};
                    options.contentType = "application/json";
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

        getIncompleteForm: function (sessionId) {

            var user = FormplayerFrontend.request('currentUser');
            var formplayerUrl = user.formplayer_url;

            var menus = new Entities.MenuSelectCollection({

                fetch: function (options) {

                    options.data = JSON.stringify({
                        "sessionId": sessionId,
                    });

                    options.url = formplayerUrl + '/incomplete-form';
                    options.type = 'POST';
                    options.dataType = "json";
                    options.crossDomain = {crossDomain: true};
                    options.xhrFields = {withCredentials: true};
                    options.contentType = "application/json";
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
    };

    FormplayerFrontend.reqres.setHandler("getIncompleteForm", function (sessionId) {
        return API.getIncompleteForm(sessionId);
    });

    FormplayerFrontend.reqres.setHandler("sessions", function () {
        return API.getSessions();
    });
});