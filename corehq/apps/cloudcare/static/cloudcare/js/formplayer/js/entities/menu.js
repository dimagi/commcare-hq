FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $, _) {

    Entities.UserModel = Backbone.Model.extend({});

    Entities.MenuSelect = Backbone.Model.extend({
        urlRoot: "menuSelects"
    });

    Entities.MenuSelectCollection = Backbone.Collection.extend({

        model: Entities.MenuSelect,

        parse: function (response) {
            this.sequenceId = response.seq_id;
            this.title = response.title;

            if (response.commands) {
                this.type = "commands";
                return response.commands;
            }
            else if (response.entities) {
                this.type = "entities";
                this.action = response.action;
                this.styles = response.styles;
                return response.entities;
            }
            else if (response.details) {
                this.type = "details";
                this.styles = response.styles;
                this.headers = response.headers;
                this.details = response.details;

                var model = [];
                for (i = 0; i < this.details.length; i += 1) {
                    current = {'header': this.headers[i], 'data': this.details[i]};
                    model.push(current)
                }
                return model;
            }
        },

        initialize: function (params) {
            this.domain = params.domain;
            this.app_id = params.app_id;
            this.fetch = params.fetch;
            this.sequenceId = params.sequenceId;
            this.selection = params.selection;
        }
    });

    var API = {

        getDetail: function (model) {

            var defer = $.Deferred();
            var mCollection = new Backbone.Collection.extend({
                fetch: function(){
                    return model.options.model.attributes.detail
                },
                initialize: function (params) {
                    this.fetch = params.fetch;
                }
            });
            mCollection.fetch({
                success: function(request) {
                    deger.resolve(request);
                }
            });
            return defer.promise();
        },

        getMenus: function (app_id, select_list) {
            var menus = new Entities.MenuSelectCollection({
                domain: FormplayerFrontend.request('currentUser').domain,
                app_id: app_id,

                fetch: function (options) {
                    var collection = this;

                    options.data = JSON.stringify({
                        "username": "test",
                        "password": "123",
                        "domain": "test",
                        "app_id": collection.app_id,
                        "selections": select_list
                    });

                    if (select_list) {
                        options.data.selections = select_list;
                    }

                    options.url = 'http://localhost:8080/navigate_menu';
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
            return defer.promise();
        },
    };

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (app_id, select_list) {
        return API.getMenus(app_id, select_list);
    });

    FormplayerFrontend.reqres.setHandler("app:get:detail", function (model) {
        return API.getDetail(model);
    });
});