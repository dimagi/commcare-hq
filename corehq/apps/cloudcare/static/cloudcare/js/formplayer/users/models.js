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

        trackVersionChange: function(model) {
            window.analytics.workflow(
                'App preview version changed',
                {
                    previousVersion: model.previous('versionInfo'),
                    currentVersion: model.get('versionInfo'),
                }
            );
        },
    });
});
