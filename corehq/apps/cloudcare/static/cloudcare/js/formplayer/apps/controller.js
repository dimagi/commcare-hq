/*global FormplayerFrontend */

FormplayerFrontend.module("Apps", function (Apps, FormplayerFrontend, Backbone, Marionette, $) {
    var views = hqImport("cloudcare/js/formplayer/apps/views");
    Apps.Controller = {
        listApps: function () {
            $.when(FormplayerFrontend.request("appselect:apps")).done(function (apps) {
                var appGridView = views.GridView({
                    collection: apps,
                });
                FormplayerFrontend.regions.getRegion('main').show(appGridView);
            });
        },
        /**
         * singleApp
         *
         * Renders a SingleAppView.
         */
        singleApp: function (appId) {
            $.when(FormplayerFrontend.request("appselect:apps")).done(function (apps) {
                var singleAppView = views.SingleAppView({
                    appId: appId,
                });
                FormplayerFrontend.regions.getRegion('main').show(singleAppView);
            });
        },
        landingPageApp: function (appId) {
            $.when(FormplayerFrontend.request("appselect:apps")).done(function (apps) {
                var landingPageAppView = views.LandingPageAppView({
                    appId: appId,
                });
                FormplayerFrontend.regions.getRegion('main').show(landingPageAppView);
            });
        },
        listSettings: function () {
            var currentUser = FormplayerFrontend.request('currentUser'),
                settings = [],
                collection,
                settingsView;
            if (currentUser.environment === FormplayerFrontend.Constants.PREVIEW_APP_ENVIRONMENT) {
                settings = settings.concat([
                    new Backbone.Model({ slug: FormplayerFrontend.Layout.Views.SettingSlugs.SET_LANG }),
                    new Backbone.Model({ slug: FormplayerFrontend.Layout.Views.SettingSlugs.SET_DISPLAY }),
                ]);
            } else {
                settings.push(
                    new Backbone.Model({ slug: FormplayerFrontend.Layout.Views.SettingSlugs.BREAK_LOCKS })
                );
            }
            settings.push(
                new Backbone.Model({ slug: FormplayerFrontend.Layout.Views.SettingSlugs.CLEAR_USER_DATA })
            );
            collection = new Backbone.Collection(settings);
            settingsView = new FormplayerFrontend.Layout.Views.SettingsView({
                collection: collection,
            });

            FormplayerFrontend.regions.getRegion('main').show(settingsView);
        },
    };
});
