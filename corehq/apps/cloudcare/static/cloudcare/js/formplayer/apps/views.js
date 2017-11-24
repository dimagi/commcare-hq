/*global FormplayerFrontend */

FormplayerFrontend.module("Apps.Views", function (Views, FormplayerFrontend, Backbone, Marionette) {
    Views.GridItem = Marionette.ItemView.extend({
        template: "#row-template",
        tagName: "div",
        className: "grid-item col-xs-6 col-sm-4 col-lg-3 formplayer-request",
        events: {
            "click": "rowClick",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("app:select", this.model.get('_id'));
        },
    });

    Views.BaseAppView = {
        events: {
            'click .js-incomplete-sessions-item': 'incompleteSessionsClick',
            'click .js-sync-item': 'syncClick',
            'click .js-restore-as-item': 'onClickRestoreAs',
            'click .js-settings': 'onClickSettings',
        },
        incompleteSessionsClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("sessions");
        },
        syncClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("sync");
        },
        onClickRestoreAs: function(e) {
            e.preventDefault();
            FormplayerFrontend.trigger("restore_as:list", this.appId);
        },
        onClickSettings: function(e) {
            e.preventDefault();
            FormplayerFrontend.trigger("settings:list");
        },
    };

    Views.GridView = Marionette.CompositeView.extend({
        template: "#grid-template",
        childView: Views.GridItem,
        childViewContainer: ".js-application-container",

        events: _.extend(Views.BaseAppView.events),
        incompleteSessionsClick: _.extend(Views.BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(Views.BaseAppView.syncClick),
        onClickRestoreAs: _.extend(Views.BaseAppView.onClickRestoreAs),
        onClickSettings: _.extend(Views.BaseAppView.onClickSettings),
    });

    /**
     * SingleAppView
     *
     * This provides a view for when previewing an application of a known id.
     * The user doesn't need to select the application because we already have
     * that information. Used for phone previewing in the app manager
     */
    Views.SingleAppView = Marionette.ItemView.extend({
        template: "#single-app-template",
        className: 'single-app-view',

        events: _.extend({
            'click .js-start-app': 'startApp',
        }, Views.BaseAppView.events),
        incompleteSessionsClick: _.extend(Views.BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(Views.BaseAppView.syncClick),
        onClickRestoreAs: _.extend(Views.BaseAppView.onClickRestoreAs),
        onClickSettings: _.extend(Views.BaseAppView.onClickSettings),

        initialize: function(options) {
            this.appId = options.appId;
        },
        templateHelpers: function() {
            var currentApp = FormplayerFrontend.request("appselect:getApp", this.appId),
                appName;
            appName = currentApp.get('name');
            return {
                showIncompleteForms: function () {
                    return FormplayerFrontend
                        .request('getAppDisplayProperties')['cc-show-incomplete'] === 'yes';
                },
                appName: appName,
            };
        },
        startApp: function(e) {
            e.preventDefault();
            hqImport('analytix/js/kissmetrics').track.event("[app-preview] User clicked Start App");
            hqImport('analytix/js/google').track.event("App Preview", "User clicked Start App");
            FormplayerFrontend.trigger("app:select", this.appId);
        },
    });

    Views.LandingPageAppView = Marionette.ItemView.extend({
        template: "#landing-page-app-template",
        className: 'landing-page-app-view',

        events: _.extend({
            'click .js-start-app': 'startApp',
        }, Views.BaseAppView.events),
        incompleteSessionsClick: _.extend(Views.BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(Views.BaseAppView.syncClick),
        onClickRestoreAs: _.extend(Views.BaseAppView.onClickRestoreAs),
        onClickSettings: _.extend(Views.BaseAppView.onClickSettings),

        initialize: function(options) {
            this.appId = options.appId;
        },
        templateHelpers: function() {
            var currentApp = FormplayerFrontend.request("appselect:getApp", this.appId),
                appName = currentApp.get('name');
            return {
                appName: appName,
            };
        },
        startApp: function() {
            FormplayerFrontend.trigger("app:select", this.appId);
        },
    });

})
;
