FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {
    Entities.AppSelect = Backbone.Model.extend({
        urlRoot: "appSelects"
    });

    Entities.configureStorage("FormplayerFrontend.Entities.AppSelect");

    Entities.AppSelectCollection = Backbone.Collection.extend({
        url: "appSelects",
        model: Entities.AppSelect,
    });

    Entities.configureStorage("FormplayerFrontend.Entities.AppSelectCollection");

    var storeApps = function (apps) {
        var old_apps = new Entities.AppSelectCollection();
        var defer = $.Deferred();
        old_apps.fetch({
            success: function (data) {
                defer.resolve(data);
            },
        });
        var promise = defer.promise();
        $.when(promise).done(function (oldApps) {
            // clear app's local storage when we load new list of apps
            window.localStorage.clear();
            apps = new Entities.AppSelectCollection(apps);
            apps.forEach(function (app) {
                app.save();
            });
            oldApps.reset(apps.models);
        });
        return promise;
    };

    var API = {
        getAppEntities: function () {
            var apps = new Entities.AppSelectCollection();
            var defer = $.Deferred();
            apps.fetch({
                success: function (request) {
                    defer.resolve(request);
                },
            });
            return defer.promise();
        },

        storeApps: function (apps) {
            storeApps(apps);
        },
    };

    FormplayerFrontend.reqres.setHandler("appselect:apps", function () {
        return API.getAppEntities();
    });

    FormplayerFrontend.reqres.setHandler("appselect:storeapps", function (apps) {
        return API.storeApps(apps);
    });
});