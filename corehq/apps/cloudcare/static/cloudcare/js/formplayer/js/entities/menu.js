FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $, _) {

    Entities.UserModel = Backbone.Model.extend({

    });

    Entities.MenuSelect = Backbone.Model.extend({
        urlRoot: "menuSelects"
    });

    Entities.MenuSelectCollection = Backbone.Collection.extend({

        model: Entities.MenuSelect,

        parse: function (response) {
            this.sessionId = response.session_id;
            this.sequenceId = response.sequenceId;
            FormplayerFrontend.request('currentUser').sessionId = this.sessionId;
            if(response.commands){
                this.type = "commands";
                return response.commands;
            } else if(response.entities){
                this.type = "entities";
                return response.entities;
            }
        },

        initialize: function (params) {
            this.domain = params.domain;
            this.app_id = params.app_id;
            this.fetch = params.fetch;
            this.sessionId = params.sessionId;
            this.sequenceId = params.sequenceId;
            this.selection = params.selection;
        }
    });

    var API = {

        getMenus: function (app_id) {
            var menus = new Entities.MenuSelectCollection({
                domain: FormplayerFrontend.request('currentUser').domain,
                app_id: app_id,

                fetch: function (options) {
                    var collection = this;
                    options.data = JSON.stringify({
                        "install_reference": "http://localhost:8000/a/" + this.domain +
                        "/apps/api/download_ccz/?app_id=" + this.app_id + "#hack=commcare.ccz",
                        "username": "test",
                        "password": "123",
                        "domain": collection.domain,
                        "app_id": collection.app_id
                    });
                    options.url = 'http://localhost:8080/install';
                    options.type = 'POST';
                    options.dataType = "json";
                    options.contentType = "application/json";
                    return Backbone.Collection.prototype.fetch.call(this, options);
                },

                initialize: function (params) {
                    this.domain = params.domain;
                    this.app_id = params.app_id;
                    this.fetch = params.fetch;
                }
            });

            var defer = $.Deferred();
            menus.fetch({
                success: function (request) {
                    defer.resolve(request);
                }
            });
            var promise = defer.promise();
            return promise;
        },

        selectMenu: function (menu) {
            var menus = new Entities.MenuSelectCollection({
                selection: menu,
                sessionId: FormplayerFrontend.request('currentUser').sessionId,

                fetch: function (options) {
                    var collection = this;
                    options.data = JSON.stringify({
                        "selection": collection.selection,
                        "session_id": collection.sessionId
                    });
                    options.url = 'http://localhost:8080/menu_select';
                    options.type = 'POST';
                    options.dataType = "json";
                    options.contentType = "application/json";
                    return Backbone.Collection.prototype.fetch.call(this, options);
                },

                initialize: function (params) {
                    this.selection = params.selection;
                    this.sessionId = params.sessionId;
                    this.fetch = params.fetch;
                }
            });
            var defer = $.Deferred();
            menus.fetch({
                success: function (request, response, whatever) {
                    defer.resolve(request);
                }
            });
            return defer.promise();
        },


    };

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (app) {
        return API.getMenus(app);
    });

    FormplayerFrontend.reqres.setHandler("app:select:menus:select", function (menu) {
        return API.selectMenu(menu);
    });
});