/*global FormplayerFrontend */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {
    Entities.AppModel = Backbone.Model.extend({
        urlRoot: "appSelects",
        idAttribute: "_id",
    });

    Entities.AppCollection = Backbone.Collection.extend({
        url: "appSelects",
        model: Entities.AppModel,
    });

    var API = {
        getAppEntities: function () {
            var appsJson = FormplayerFrontend.request('currentUser').apps;
            var apps = new Entities.AppCollection(appsJson);
            return apps;
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