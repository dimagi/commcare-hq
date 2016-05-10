FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $, _) {
    Entities.AppSelect = Backbone.Model.extend({
        urlRoot: "appSelects"
    });

    Entities.configureStorage("FormplayerFrontend.Entities.AppSelect");

    Entities.AppSelectCollection = Backbone.Collection.extend({
        url: "appSelects",
        model: Entities.AppSelect
    });

    Entities.configureStorage("FormplayerFrontend.Entities.AppSelectCollection");

    var storeApps = function (apps) {

        old_apps = new Entities.AppSelectCollection();
        var defer = $.Deferred();
        old_apps.fetch({
            success: function (data) {
                defer.resolve(data);
            }
        });

        var promise = defer.promise();
        $.when(promise).done(function (oldApps) {
            if (oldApps.length === 0) {
                apps = new Entities.AppSelectCollection(apps);
                apps.forEach(function (app) {
                    console.log("Storing app: " + app);
                    app.save();
                });
                oldApps.reset(apps.models);
            }
        });
        return promise;
    };

    var API = {
        getAppEntities: function () {
            var apps = new Entities.AppSelectCollection();
            var defer = $.Deferred();
            apps.fetch({
                success: function (data) {
                    defer.resolve(data);
                }
            });
            var promise = defer.promise();
            console.log("Get App Entities");
            return promise;
        },

        storeApps: function (apps) {
            storeApps(apps);
        }
    };

    FormplayerFrontend.reqres.setHandler("appselect:apps", function () {
        return API.getAppEntities();
    });

    FormplayerFrontend.reqres.setHandler("appselect:storeapps", function (apps) {
        console.log("app selection store apps");
        return API.storeApps(apps);
    })
});