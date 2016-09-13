/*global FormplayerFrontend, Util */

/**
 * Backbone model for listing and selecting CommCare menus (modules, forms, and cases)
 */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {

    Entities.MenuSelect = Backbone.Model.extend({});

    Entities.MenuSelectCollection = Backbone.Collection.extend({

        model: Entities.MenuSelect,

        parse: function (response) {
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
            }
            else if (response.entities) {
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
            }
            else if(response.type === "query") {
                return response.displays;
            }
            else if(response.tree){
                // form entry time, doggy
                FormplayerFrontend.trigger('startForm', response, this.app_id);
            }
            else if(response.exception){
                FormplayerFrontend.request('showError', response.exception);
            }
        },

        initialize: function (params) {
            this.domain = params.domain;
            this.appId = params.appId;
            this.fetch = params.fetch;
            this.selection = params.selection;
        },
    });

    var API = {

        getMenus: function (params) {

            var user = FormplayerFrontend.request('currentUser');
            var username = user.username;
            var domain = user.domain;
            var language = user.language;
            var formplayerUrl = user.formplayer_url;

            var menus = new Entities.MenuSelectCollection({

                appId: params.appId,

                fetch: function (options) {
                    var collection = this;

                    options.data = JSON.stringify({
                        "username": user.username,
                        "domain": domain,
                        "app_id": collection.appId,
                        "locale": language,
                        "selections": params.steps,
                        "offset": params.page * 10,
                        "search_text": params.search,
                        "menu_session_id": params.sessionId,
                        "query_dictionary": params.queryDict,
                        "previewCommand": params.previewCommand,
                        "installReference": params.installReference,
                    });

                    if (options.steps) {
                        options.data.selections = params.steps;
                    }

                    options.url = formplayerUrl + '/navigate_menu';
                    Util.setCrossDomainAjaxOptions(options);
                    return Backbone.Collection.prototype.fetch.call(this, options);
                },

            });

            var defer = $.Deferred();
            menus.fetch({
                success: function (request) {
                    defer.resolve(request);
                },
                error: function (request) {
                    FormplayerFrontend.request(
                        'showError',
                        gettext('Unable to connect to form playing service. ' +
                                'Please report an issue if you continue to see this message.')
                    );
                    defer.resolve(request);
                },
            });
            return defer.promise();
        },
    };

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (options) {
        return API.getMenus(options);
    });
});
