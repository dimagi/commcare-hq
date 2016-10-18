/*global FormplayerFrontend, Util */

/**
 * Backbone model for listing and selecting CommCare menus (modules, forms, and cases)
 */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {

    Entities.MenuSelect = Backbone.Model.extend({});

    Entities.MenuSelectCollection = Backbone.Collection.extend({

        model: Entities.MenuSelect,

        parse: function (response, request) {
            this.title = response.title;
            this.type = response.type;
            this.clearSession = response.clearSession;
            this.notification = response.notification;
            this.breadcrumbs = response.breadcrumbs;
            this.appVersion = response.appVersion;
            this.appId = response.appId;
            this.persistentCaseTile = response.persistentCaseTile;

            if (response.commands) {
                this.type = "commands";
                return response.commands;
            } else if (response.entities) {
                this.action = response.action;
                this.styles = response.styles;
                this.headers = response.headers;
                this.widthHints = response.widthHints;
                this.currentPage = response.currentPage;
                this.pageCount = response.pageCount;
                this.tiles = response.tiles;
                this.numEntitiesPerRow = response.numEntitiesPerRow;
                this.maxWidth = response.maxWidth;
                this.maxHeight = response.maxHeight;
                return response.entities;
            } else if(response.type === "query") {
                return response.displays;
            } else if(response.tree){
                // form entry time, doggy
                FormplayerFrontend.trigger('startForm', response, this.app_id);
            } 
        },

        sync: function (method, model, options) {
            Util.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });

    var API = {

        getMenus: function (params) {

            var user = FormplayerFrontend.request('currentUser');
            var username = user.username;
            var domain = user.domain;
            var language = user.language;
            var formplayerUrl = user.formplayer_url;
            var displayOptions = user.displayOptions || {};
            var defer = $.Deferred();
            var menus;
            var options = {
                success: function (parsedMenus, response) {
                    if (response.status === 'retry') {
                        FormplayerFrontend.trigger('retry', response, function() {
                            menus.fetch($.extend(true, {}, options));
                        }, gettext('Please wait while we sync your user...'));
                    } else if (response.exception){
                        FormplayerFrontend.trigger(
                            'showError',
                            response.exception,
                            response.type === 'html'
                        );
                    } else {
                        FormplayerFrontend.trigger('clearProgress');
                        defer.resolve(parsedMenus);
                    }
                },
                error: function () {
                    FormplayerFrontend.request(
                        'showError',
                        gettext('Unable to connect to form playing service. ' +
                                'Please report an issue if you continue to see this message.')
                    );
                    defer.resolve();
                },
            };

            options.data = JSON.stringify({
                "username": user.username,
                "domain": domain,
                "app_id": params.appId,
                "locale": language,
                "selections": params.steps,
                "offset": params.page * 10,
                "search_text": params.search,
                "menu_session_id": params.sessionId,
                "query_dictionary": params.queryDict,
                "previewCommand": params.previewCommand,
                "installReference": params.installReference,
                "oneQuestionPerScreen": ko.utils.unwrapObservable(displayOptions.oneQuestionPerScreen),
            });
            options.url = formplayerUrl + '/navigate_menu';

            menus = new Entities.MenuSelectCollection();

            Object.freeze(options)
            menus.fetch($.extend(true, {}, options));
            return defer.promise();
        },
    };

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (options) {
        return API.getMenus(options);
    });
});
