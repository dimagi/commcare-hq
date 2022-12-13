'use strict';
hqDefine("cloudcare/js/formplayer/apps/controller", [
    'jquery',
    'backbone',
    'hqwebapp/js/toggles',
    'cloudcare/js/formplayer/constants',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/layout/views/settings',
    'cloudcare/js/formplayer/apps/views',
    'cloudcare/js/formplayer/apps/api'  // appselect:apps
], function (
    $,
    Backbone,
    Toggles,
    constants,
    FormplayerFrontend,
    settingsViews,
    views
) {
    return {
        listApps: function () {
            $.when(FormplayerFrontend.getChannel().request("appselect:apps")).done(function (appCollection) {
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
            if (Toggles.toggleEnabled('HIDE_SYNC_BUTTON')) {
                settings.push(
                    new Backbone.Model({ slug: slugs.SYNC })
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
