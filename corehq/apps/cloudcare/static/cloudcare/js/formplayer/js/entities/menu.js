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

            if (response.commands) {
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
                return response.entities;
            }
            else if(response.type === "query") {
                return response.displays;
            }
            else if(response.tree){
                // form entry time, doggy
                FormplayerFrontend.request('startForm', response, this.app_id);
            }
            else if(response.exception){
                FormplayerFrontend.request('error', response.exception);
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

        getMenus: function (appId, sessionId, stepList, page, search, queryDict) {

            var user = FormplayerFrontend.request('currentUser');
            var username = user.username;
            var domain = user.domain;
            var language = user.language;
            var formplayerUrl = user.formplayer_url;
            var trimmedUsername = username.substring(0, username.indexOf("@"));

            var menus = new Entities.MenuSelectCollection({

                appId: appId,

                fetch: function (options) {
                    var collection = this;

                    options.data = JSON.stringify({
                        "username": trimmedUsername,
                        "domain": domain,
                        "app_id": collection.appId,
                        "locale": language,
                        "selections": stepList,
                        "offset": page * 10,
                        "search_text": search,
                        "menu_session_id": sessionId,
                        "query_dictionary": queryDict,
                    });

                    if (stepList) {
                        options.data.selections = stepList;
                    }

                    options.url = formplayerUrl + '/navigate_menu';
                    Util.setCrossDomainAjaxOptions(options);
                    return Backbone.Collection.prototype.fetch.call(this, options);
                },

                initialize: function (params) {
                    this.domain = params.domain;
                    this.appId = params.appId;
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

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (appId, sessionId, stepList, page, search, queryDict) {
        return API.getMenus(appId, sessionId, stepList, page, search, queryDict);
    });
});