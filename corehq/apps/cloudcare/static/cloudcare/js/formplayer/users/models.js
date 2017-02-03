/*global FormplayerFrontend */

FormplayerFrontend.module("Users.Models", function(Models, FormplayerFrontend, Backbone) {
    Models.User = Backbone.Model.extend();
    Models.CurrentUser = Backbone.Model.extend({
        initialize: function() {
            this.on('change:versionInfo', function(model) {
                if (model.previous('versionInfo') && model.get('versionInfo')) {
                    this.trackVersionChange(model);
                }
            }.bind(this));
        },

        isMobileWorker: function() {
            return this.username.endsWith('commcarehq.org');
        },

        getDisplayUsername: function() {
            if (this.isMobileWorker()) {
                return this.username.split('@')[0];
            }
            return this.username;
        },

        trackVersionChange: function(model) {
            window.analytics.workflow(
                '[app-preview] App version changed',
                {
                    previousVersion: model.previous('versionInfo'),
                    currentVersion: model.get('versionInfo'),
                }
            );
        },
    });
});
