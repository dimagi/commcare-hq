/*global FormplayerFrontend */

/**
 * Backbone model and functions for listing and selecting CommCare apps
 */

FormplayerFrontend.module("Apps", function (Apps, FormplayerFrontend, Backbone) {
    var appsPromiseByRestoreAs = {};
    var appsByRestoreAs = {};
    var predefinedAppsPromise;

    function fetchAllApps(restoreAs) {
        var appsPromise = appsPromiseByRestoreAs[restoreAs];
        if (!appsPromise || appsPromise.state() === 'rejected') {
            appsPromise = appsPromiseByRestoreAs[restoreAs] = $.getJSON('?option=apps');
        }
        return appsPromise;
    }

    function fetchPredefinedApps() {
        /*
          in singleAppMode we want to avoid calling the server when we switch users because
          1. it is unnecessary, since there's only one app regardless of restoreAs user
          2. the backend ?option=apps endpoint is not defined for single-app pages
       */
        return predefinedAppsPromise;
    }

    Apps.API = {
        primeApps: function (restoreAs, apps) {
            appsPromiseByRestoreAs[restoreAs] = predefinedAppsPromise = $.Deferred().resolve(apps);
        },
        getAppEntities: function () {
            var appsPromise,
                restoreAs = FormplayerFrontend.request('currentUser').restoreAs,
                singleAppMode = FormplayerFrontend.request('currentUser').displayOptions.singleAppMode;
            if (singleAppMode) {
                appsPromise = fetchPredefinedApps();
            } else {
                appsPromise = fetchAllApps(restoreAs);
            }
            return appsPromise.pipe(function (apps) {
                appsByRestoreAs[restoreAs] = apps;
                return hqImport("cloudcare/js/formplayer/apps/collections")(apps);
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
            var appCollection = hqImport("cloudcare/js/formplayer/apps/collections")(apps);
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
