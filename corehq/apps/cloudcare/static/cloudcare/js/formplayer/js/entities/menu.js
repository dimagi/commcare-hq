FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $, _) {
    Entities.MenuSelect = Backbone.Model.extend({
        urlRoot: "menuSelects"
    });

    Entities.configureStorage("FormplayerFrontend.Entities.MenuSelect");

    Entities.MenuSelectCollection = Backbone.Collection.extend({

        initialize: function (app) {
            this.profileRef = "commcarehq.org/a/" + app.attributes.domain +
                "/apps/download/" + app.attributes._id + "/profile.ccpr";
            console.log("init profile ref: " + this.profileRef);
        },

        url: function () {
            return this.profileRef;
        },

        fetch: function () {
            var collection = this;
            debugger;
            console.log("fetching");
            $.ajax({
                type: 'POST',
                url: 'http://localhost:8080/install',
                traditional : true,
                contentType : "application/json",
                dataType : "json",
                data: JSON.stringify({
                    "install_reference" : collection.profileRef,
                    "username" : "test",
                    "password" : "123",
                    "domain" : "test"
                }),
                success: function (data) {
                    console.log(data);
                    // set collection data (assuming you have retrieved a json object)
                    collection.reset(data)
                }
            });
        },
        model: Entities.MenuSelect
    });

    Entities.configureStorage("FormplayerFrontend.Entities.MenuSelectCollection");

    var API = {
        getMenus: function (app) {
            console.log("API Get Menus: " + app);
            var apps = new Entities.MenuSelectCollection(app);
            var defer = $.Deferred();
            apps.fetch({
                success: function (data) {
                    defer.resolve(data);
                }
            });
            var promise = defer.promise();
            return promise;
        },
    };

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (app) {
        console.log("menu entities get items: " + app);
        return API.getMenus(app);
    });
});