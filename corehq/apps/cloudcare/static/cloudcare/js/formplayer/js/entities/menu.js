FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $, _) {
    Entities.MenuSelect = Backbone.Model.extend({
        urlRoot: "menuSelects"
    });

    Entities.MenuSelectCollection = Backbone.Collection.extend({

        model: Entities.MenuSelect,

        parse: function(response, options) {
            return response.commands;
        },

        initialize: function (params) {
            this.profileRef = "http://localhost:8000/a/" + params.domain +
                "/apps/api/download_ccz/?app_id=" + params.app_id + "#hack=commcare.ccz";
            console.log("init profile ref: " + this.profileRef);
        },

        fetch: function (options) {
            var collection = this;
            options.data = JSON.stringify({
                "install_reference": collection.profileRef,
                "username": "test",
                "password": "123",
                "domain": "test"
            });
            options.url = 'http://localhost:8080/install';
            options.type = 'POST';
            options.dataType = "json";
            options.contentType = "application/json";
            return Backbone.Collection.prototype.fetch.call(this, options);
        }
    });

    var API = {
        getMenus: function (app) {
            console.log("API Get Menus: " + app);
            var menus = new Entities.MenuSelectCollection({domain: app.attributes.domain, app_id: app.attributes._id});
            var defer = $.Deferred();
            menus.fetch({
                success: function (request) {
                    defer.resolve(request);
                }
            });
            var promise = defer.promise();
            return promise;
        },
    };

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (app) {
        return API.getMenus(app);
    });
});