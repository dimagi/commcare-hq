'use strict';
/**
 * Backbone model and functions for listing and selecting CommCare apps
 */
hqDefine("cloudcare/js/formplayer/apps/api", [
    'jquery',
    'cloudcare/js/formplayer/apps/collections',
    'cloudcare/js/formplayer/app',
], function (
    $,
    Collections,
    FormplayerFrontend
) {
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

    var API = {
        primeApps: function (restoreAs, apps) {
            appsPromiseByRestoreAs[restoreAs] = predefinedAppsPromise = $.Deferred().resolve(apps);
        },
        getAppEntities: function () {
            var appsPromise,
                restoreAs = FormplayerFrontend.getChannel().request('currentUser').restoreAs,
                singleAppMode = FormplayerFrontend.getChannel().request('currentUser').displayOptions.singleAppMode;
            if (singleAppMode) {
                appsPromise = fetchPredefinedApps();
            } else {
                appsPromise = fetchAllApps(restoreAs);
            }
            return appsPromise.pipe(function (apps) {
                appsByRestoreAs[restoreAs] = apps;
                return Collections(apps);
            });
        },
        getAppEntity: function (id) {
            var restoreAs = FormplayerFrontend.getChannel().request('currentUser').restoreAs;
            var apps = appsByRestoreAs[restoreAs];
            if (!apps) {
                console.warn("getAppEntity is returning null. If the app_id is correct, " +
                             "it may have been called before getAppEntities populated it asynchronously.");
                return null;
            }
            var appCollection = Collections(apps);
            return appCollection.get(id);
        },
    };

    FormplayerFrontend.getChannel().reply("appselect:apps", function () {
        return API.getAppEntities();
    });

    FormplayerFrontend.getChannel().reply("appselect:getApp", function (id) {
        return API.getAppEntity(id);
    });

    return API;
});
