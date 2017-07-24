/*global FormplayerFrontend */

FormplayerFrontend.module("Apps", function(Apps, FormplayerFrontend, Backbone, Marionette, $){
    Apps.Controller = {
        listApps: function(){
            var fetchingApps = FormplayerFrontend.request("appselect:apps");

            $.when(fetchingApps).done(function (apps) {

                var appGridView = new Apps.Views.GridView({
                    collection: apps,
                });

                FormplayerFrontend.regions.main.show(appGridView);
            });
        },
        /**
         * singleApp
         *
         * Renders a SingleAppView.
         */
        singleApp: function(appId) {
            var singleAppView = new Apps.Views.SingleAppView({
                appId: appId,
            });
            FormplayerFrontend.regions.main.show(singleAppView);
        },
        landingPageApp: function(appId) {
            var landingPageAppView = new Apps.Views.LandingPageAppView({
                appId: appId,
            });
            FormplayerFrontend.regions.main.show(landingPageAppView);
        },
        listSettings: function() {
            var collection = new Backbone.Collection([
                new Backbone.Model({ slug: FormplayerFrontend.Layout.Views.SettingSlugs.SET_LANG }),
                new Backbone.Model({ slug: FormplayerFrontend.Layout.Views.SettingSlugs.SET_DISPLAY }),
            ]);
            var settingsView = new FormplayerFrontend.Layout.Views.SettingsView({
                collection: collection,
            });
            FormplayerFrontend.regions.main.show(settingsView);
        },
    };
});
