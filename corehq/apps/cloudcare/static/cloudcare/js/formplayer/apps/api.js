/*global FormplayerFrontend */

/**
 * Backbone model and functions for listing and selecting CommCare apps
 */

FormplayerFrontend.module("Apps", function (Apps, FormplayerFrontend, Backbone) {

    var appsPromiseByRestoreAs = {};

    Apps.API = {
        primeApps: function (restoreAs, apps) {
            appsPromiseByRestoreAs[restoreAs] = $.Deferred().resolve(apps);
        },
        getAppEntities: function () {
            var restoreAs = FormplayerFrontend.request('currentUser').restoreAs;
            var appsPromise = appsPromiseByRestoreAs[FormplayerFrontend.request('currentUser').restoreAs];
            if (!appsPromise || appsPromise.state() == 'rejected') {
                appsPromise = appsPromiseByRestoreAs[restoreAs] = $.getJSON('?option=apps');
            }
            return appsPromise.pipe(function (apps) {
                return new FormplayerFrontend.Apps.Collections.App(apps);
            });
        },
        getAppEntity: function (app_id) {
            var apps = Apps.API.getAppEntities();
            return apps.get(app_id);
        },
    };

    FormplayerFrontend.reqres.setHandler("appselect:apps", function () {
        return Apps.API.getAppEntities();
    });

    FormplayerFrontend.reqres.setHandler("appselect:getApp", function (app_id) {
        return Apps.API.getAppEntity(app_id);
    });
});
