/*global FormplayerFrontend */

/**
 * Backbone model and functions for listing and selecting CommCare apps
 */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone) {

    var API = {
        getAppEntities: function () {
            var appsJson = FormplayerFrontend.request('currentUser').apps;
            return new FormplayerFrontend.Apps.Collections.App(appsJson);
        },
        getAppEntity: function (app_id) {
            var apps = API.getAppEntities();
            return apps.get(app_id);
        },
    };

    FormplayerFrontend.reqres.setHandler("appselect:apps", function () {
        return API.getAppEntities();
    });

    FormplayerFrontend.reqres.setHandler("appselect:getApp", function (app_id) {
        return API.getAppEntity(app_id);
    });
});
