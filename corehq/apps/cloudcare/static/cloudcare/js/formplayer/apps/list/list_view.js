/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.AppList", function (AppList, FormplayerFrontend, Backbone, Marionette) {
    AppList.GridItem = Marionette.ItemView.extend({
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

    AppList.BaseAppView = {
        events: {
            'click .js-incomplete-sessions-item': 'incompleteSessionsClick',
            'click .js-sync-item': 'syncClick',
        },
        incompleteSessionsClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("sessions");
        },
        syncClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("sync");
        },
    };

    AppList.GridView = Marionette.CompositeView.extend({
        template: "#grid-template",
        childView: AppList.GridItem,
        childViewContainer: ".js-application-container",

        events: _.extend(AppList.BaseAppView.events),
        incompleteSessionsClick: _.extend(AppList.BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(AppList.BaseAppView.syncClick),
    });

    /**
     * SingleAppView
     *
     * This provides a view for when previewing an application of a known id.
     * The user doesn't need to select the application because we already have
     * that information. Used for phone previewing in the app manager
     */
    AppList.SingleAppView = Marionette.ItemView.extend({
        template: "#single-app-template",
        className: 'single-app-view',

        events: _.extend({
            'click .js-start-app': 'startApp',
        }, AppList.BaseAppView.events),
        incompleteSessionsClick: _.extend(AppList.BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(AppList.BaseAppView.syncClick),

        initialize: function(options) {
            this.appId = options.appId;
        },
        templateHelpers: function() {
            return {
                showIncompleteForms: function () {
                    return FormplayerFrontend
                        .request('getAppDisplayProperties')['cc-show-incomplete'] === 'yes';
                },
            };
        },
        startApp: function(e) {
            e.preventDefault();
            FormplayerFrontend.trigger("app:select", this.appId);
        },
    });
})
;
