/*global Backbone */

hqDefine("cloudcare/js/formplayer/apps/controller", function () {
    var constants = hqImport("cloudcare/js/formplayer/constants"),
        FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        settingsViews = hqImport("cloudcare/js/formplayer/layout/views/settings"),
        views = hqImport("cloudcare/js/formplayer/apps/views");
    return {
        listApps: function () {
            $.when(FormplayerFrontend.getChannel().request("appselect:apps")).done(function (apps) {
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
            $.when(FormplayerFrontend.getChannel().request("appselect:apps")).done(function () {
                var singleAppView = views.SingleAppView({
                    appId: appId,
                });
                FormplayerFrontend.regions.getRegion('main').show(singleAppView);
            });
        },
        landingPageApp: function (appId) {
            $.when(FormplayerFrontend.getChannel().request("appselect:apps")).done(function () {
                var landingPageAppView = views.LandingPageAppView({
                    appId: appId,
                });
                FormplayerFrontend.regions.getRegion('main').show(landingPageAppView);
            });
        },
        listSettings: function () {
            var currentUser = FormplayerFrontend.getChannel().request('currentUser'),
                slugs = settingsViews.slugs,
                settings = [],
                collection,
                settingsView;
            if (currentUser.environment === constants.PREVIEW_APP_ENVIRONMENT) {
                settings = settings.concat([
                    new Backbone.Model({ slug: slugs.SET_LANG }),
                    new Backbone.Model({ slug: slugs.SET_DISPLAY }),
                ]);
            } else {
                settings.push(
                    new Backbone.Model({ slug: slugs.BREAK_LOCKS })
                );
            }
            settings.push(
                new Backbone.Model({ slug: slugs.CLEAR_USER_DATA })
            );
            collection = new Backbone.Collection(settings);
            settingsView = settingsViews.SettingsView({
                collection: collection,
            });

            FormplayerFrontend.regions.getRegion('main').show(settingsView);
        },
    };
});
