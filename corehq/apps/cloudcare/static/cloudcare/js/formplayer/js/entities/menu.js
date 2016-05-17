/*global FormplayerFrontend */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {

    Entities.MenuSelect = Backbone.Model.extend({});

    Entities.MenuSelectCollection = Backbone.Collection.extend({

        model: Entities.MenuSelect,

        parse: function (response) {
            this.title = response.title;

            if (response.commands) {
                this.type = "commands";
                return response.commands;
            }
            else if (response.entities) {
                this.type = "entities";
                this.action = response.action;
                this.styles = response.styles;
                this.headers = response.headers;
                this.widthHints = response.widthHints;
                this.currentPage = response.currentPage;
                this.pageCount = response.pageCount;
                return response.entities;
            }
            else if(response.tree){
                // form entry time, doggy
                FormplayerFrontend.request('startForm', response, this.app_id);
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

        getMenus: function (appId, stepList, page) {
            var menus = new Entities.MenuSelectCollection({
                domain: FormplayerFrontend.request('currentUser').domain,
                appId: appId,

                fetch: function (options) {
                    var collection = this;

                    options.data = JSON.stringify({
                        "username": "test",
                        "password": "123",
                        "domain": "test",
                        "app_id": collection.appId,
                        "selections": stepList,
                        "offset": page * 10,
                    });

                    if (stepList) {
                        options.data.selections = stepList;
                    }

                    options.url = 'http://localhost:8090/navigate_menu';
                    options.type = 'POST';
                    options.dataType = "json";
                    options.contentType = "application/json";
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

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (appId, stepList, page) {
        return API.getMenus(appId, stepList, page);
    });
});