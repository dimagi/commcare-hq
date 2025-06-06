define("cloudcare/js/formplayer/apps/controller", [
    'jquery',
    'backbone',
    'hqwebapp/js/toggles',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/layout/views/settings',
    'cloudcare/js/formplayer/apps/api',
    'cloudcare/js/formplayer/apps/views',
    'cloudcare/js/formplayer/users/models',
], function (
    $,
    Backbone,
    Toggles,
    FormplayerFrontend,
    settingsViews,
    AppsAPI,
    views,
    UsersModels,
) {
    return {
        listApps: function () {
            $.when(AppsAPI.getAppEntities()).done(function (appCollection) {
                let apps = appCollection.toJSON();
                let isIncompleteFormsDisabled = (app) => (app.profile.properties || {})['cc-show-incomplete'] === 'no';
                let isAllIncompleteFormsDisabled = apps.every(isIncompleteFormsDisabled);

                var appGridView = views.GridView({
                    collection: appCollection,
                    shouldShowIncompleteForms: !isAllIncompleteFormsDisabled,
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
            $.when(AppsAPI.getAppEntities()).done(function () {
                var singleAppView = views.SingleAppView({
                    appId: appId,
                });
                FormplayerFrontend.regions.getRegion('main').show(singleAppView);
            });
        },
        listSettings: function () {
            var currentUser = UsersModels.getCurrentUser(),
                slugs = settingsViews.slugs,
                settings = [],
                collection,
                settingsView;
            if (currentUser.isAppPreview) {
                settings = settings.concat([
                    new Backbone.Model({ slug: slugs.SET_LANG }),
                    new Backbone.Model({ slug: slugs.SET_DISPLAY }),
                ]);
            } else {
                settings.push(
                    new Backbone.Model({ slug: slugs.BREAK_LOCKS }),
                );
            }
            settings.push(
                new Backbone.Model({ slug: slugs.CLEAR_USER_DATA }),
            );
            if (Toggles.toggleEnabled('HIDE_SYNC_BUTTON')) {
                settings.push(
                    new Backbone.Model({ slug: slugs.SYNC }),
                );
            }
            collection = new Backbone.Collection(settings);
            settingsView = settingsViews.SettingsView({
                collection: collection,
            });

            FormplayerFrontend.regions.getRegion('main').show(settingsView);
        },
    };
});
