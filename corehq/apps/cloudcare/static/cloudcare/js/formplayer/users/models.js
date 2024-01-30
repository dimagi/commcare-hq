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
    var userInstance;
    var getCurrentUser = function () {
        if (!userInstance) {
            userInstance = new CurrentUser();
        }
        return userInstance;
    };

    return {
        User: User,
        // TODO: deprecate
        CurrentUser: function () {
            return getCurrentUser();
        },
        getCurrentUser: getCurrentUser,
    };
});
