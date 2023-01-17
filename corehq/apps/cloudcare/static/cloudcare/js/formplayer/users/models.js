'use strict';
hqDefine("cloudcare/js/formplayer/users/models", [
    "backbone",
    "analytix/js/kissmetrix",
], function (
    Backbone,
    kissmetrics
) {
    var User = Backbone.Model.extend();
    var CurrentUser = Backbone.Model.extend({
        initialize: function () {
            this.on('change:versionInfo', function (model) {
                if (model.previous('versionInfo') && model.get('versionInfo')) {
                    this.trackVersionChange(model);
                }
            }.bind(this));
        },

        isMobileWorker: function () {
            return this.username.endsWith('commcarehq.org');
        },

        getDisplayUsername: function () {
            if (this.isMobileWorker()) {
                return this.username.split('@')[0];
            }
            return this.username;
        },

        trackVersionChange: function (model) {
            kissmetrics.track.event(
                '[app-preview] App version changed',
                {
                    previousVersion: model.previous('versionInfo'),
                    currentVersion: model.get('versionInfo'),
                }
            );
        },
    });

    var saveDisplayOptions = function (displayOptions) {
        var displayOptionsKey = getDisplayOptionsKey();
        localStorage.setItem(displayOptionsKey, JSON.stringify(displayOptions));
    };

    var getSavedDisplayOptions = function () {
        var displayOptionsKey = getDisplayOptionsKey();
        try {
            return JSON.parse(localStorage.getItem(displayOptionsKey));
        } catch (e) {
            window.console.warn('Unabled to parse saved display options');
            return {};
        }
    };

    var getDisplayOptionsKey = function () {
        var user = getCurrentUser();
        return [
            user.environment,
            user.domain,
            user.username,
            'displayOptions',
        ].join(':');
    };

    var userInstance;
    var getCurrentUser = function () {
        if (!userInstance) {
            userInstance = new CurrentUser();
        }
        return userInstance;
    };

    return {
        User: User,
        getCurrentUser: getCurrentUser,
        getDisplayOptionsKey: getDisplayOptionsKey,
        getSavedDisplayOptions: getSavedDisplayOptions,
        saveDisplayOptions: saveDisplayOptions,
    };
});
