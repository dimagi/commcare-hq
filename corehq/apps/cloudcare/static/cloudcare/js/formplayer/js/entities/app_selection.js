/*global FormplayerFrontend */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {
    Entities.AppModel = Backbone.Model.extend({
        urlRoot: "appSelects",
    });

    Entities.configureStorage("FormplayerFrontend.Entities.AppModel");

    Entities.AppCollection = Backbone.Collection.extend({
        url: "appSelects",
        model: Entities.AppModel,
    });

    Entities.configureStorage("FormplayerFrontend.Entities.AppCollection");

    var storeApps = function (apps) {
        var oldApps = new Entities.AppCollection();
        var defer = $.Deferred();
        oldApps.fetch({
            success: function (data) {
                defer.resolve(data);
            },
        });
        var promise = defer.promise();
        $.when(promise).done(function (oldApps) {
            // clear app's local storage when we load new list of apps
            window.localStorage.clear();
            apps = new Entities.AppCollection(apps);
            apps.forEach(function (app) {
                app.save();
            });
            oldApps.reset(apps.models);
        });
        return promise;
    };

    var API = {
        getAppEntities: function () {
            var apps = new Entities.AppCollection();
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