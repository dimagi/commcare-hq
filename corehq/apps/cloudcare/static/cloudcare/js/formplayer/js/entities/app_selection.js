/*global FormplayerFrontend */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {
    Entities.AppModel = Backbone.Model.extend({
        urlRoot: "appSelects",
        idAttribute: "_id",
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
            var appsJson = FormplayerFrontend.request('currentUser').apps;
            var apps = new Entities.AppCollection(appsJson);
            debugger;
            return apps;
        },

        storeApps: function (apps) {
            storeApps(apps);
        },
        getAppEntity: function (app_id) {
            var apps = new Entities.AppCollection();
            apps.fetch();
            return apps.get(app_id);
        },
    };

    FormplayerFrontend.reqres.setHandler("appselect:apps", function () {
        return API.getAppEntities();
    });

    FormplayerFrontend.reqres.setHandler("appselect:storeapps", function (apps) {
        return API.storeApps(apps);
    });

    FormplayerFrontend.reqres.setHandler("appselect:getApp", function (app_id) {
        return API.getAppEntity(app_id);
    });
});