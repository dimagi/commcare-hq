/*global FormplayerFrontend */

/**
 * Backbone model and functions for listing and selecting CommCare apps
 */

FormplayerFrontend.module("Apps", function (Apps, FormplayerFrontend, Backbone) {

    var appsPromiseByRestoreAs = {};
    var appsByRestoreAs = {};

    Apps.API = {
        primeApps: function (restoreAs, apps) {
            appsPromiseByRestoreAs[restoreAs] = $.Deferred().resolve(apps);
        },
        getAppEntities: function () {
            var restoreAs = FormplayerFrontend.request('currentUser').restoreAs;
            var appsPromise = appsPromiseByRestoreAs[FormplayerFrontend.request('currentUser').restoreAs];
            if (!appsPromise || appsPromise.state() === 'rejected') {
                appsPromise = appsPromiseByRestoreAs[restoreAs] = $.getJSON('?option=apps');
            }
            return appsPromise.pipe(function (apps) {
                appsByRestoreAs[restoreAs] = apps;
                return new FormplayerFrontend.Apps.Collections.App(apps);
            });
        },
        getAppEntity: function (app_id) {
            var restoreAs = FormplayerFrontend.request('currentUser').restoreAs;
            var apps = appsByRestoreAs[restoreAs];
            if (!apps) {
                console.warn("getAppEntity is returning null. If the app_id is correct, " +
                             "it may have been called before getAppEntities populated it asynchronously.");
                return null;
            }
            var appCollection = new FormplayerFrontend.Apps.Collections.App(apps);
            return appCollection.get(app_id);
        },
    };

    FormplayerFrontend.reqres.setHandler("appselect:apps", function () {
        return Apps.API.getAppEntities();
    });

    FormplayerFrontend.reqres.setHandler("appselect:getApp", function (app_id) {
        return Apps.API.getAppEntity(app_id);
    });
});
