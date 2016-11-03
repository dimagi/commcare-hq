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
            FormplayerFrontend.regions.phoneModeNavigation.show(
                new FormplayerFrontend.Layout.Views.PhoneNavigation({ appId: appId })
            );
            FormplayerFrontend.regions.main.show(singleAppView);
            FormplayerFrontend.trigger('phone:back:hide');
        },
        listSettings: function() {
            var settingsView = new FormplayerFrontend.Layout.Views.SettingsView();
            FormplayerFrontend.regions.main.show(settingsView);
        },
    };
});
