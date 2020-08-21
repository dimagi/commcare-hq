/*global FormplayerFrontend, Marionette */

hqDefine("cloudcare/js/formplayer/apps/views", function() {
    GridItem = Marionette.LayoutView.extend({
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

        templateHelpers: function () {
            var imageUri = this.options.model.get('imageUri');
            var appId = this.options.model.get('_id');
            return {
                imageUrl: imageUri && appId ? FormplayerFrontend.request('resourceMap', imageUri, appId) : "",
            };
        },
    });

    BaseAppView = {
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
        onClickRestoreAs: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("restore_as:list", this.appId);
        },
        onClickSettings: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("settings:list");
        },
    };

    GridContainerView = Marionette.CollectionView.extend({
        childView: GridItem,
        childViewContainer: ".js-application-container",
    });

    GridView = Marionette.LayoutView.extend({
        template: "#grid-template",

        regions: {
            body: {
                el: '.js-application-container',
            },
        },
        onShow: function () {
            this.getRegion('body').show(new GridContainerView({
                collection: this.collection,
            }));
        },

        events: _.extend(BaseAppView.events),
        incompleteSessionsClick: _.extend(BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(BaseAppView.syncClick),
        onClickRestoreAs: _.extend(BaseAppView.onClickRestoreAs),
        onClickSettings: _.extend(BaseAppView.onClickSettings),
    });

    /**
     * SingleAppView
     *
     * This provides a view for when previewing an application of a known id.
     * The user doesn't need to select the application because we already have
     * that information. Used for phone previewing in the app manager
     */
    SingleAppView = Marionette.LayoutView.extend({
        template: "#single-app-template",
        className: 'single-app-view',

        events: _.extend({
            'click .js-start-app': 'startApp',
        }, BaseAppView.events),
        incompleteSessionsClick: _.extend(BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(BaseAppView.syncClick),
        onClickRestoreAs: _.extend(BaseAppView.onClickRestoreAs),
        onClickSettings: _.extend(BaseAppView.onClickSettings),

        initialize: function (options) {
            this.appId = options.appId;
        },
        templateHelpers: function () {
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
        startApp: function (e) {
            e.preventDefault();
            hqImport('analytix/js/kissmetrix').track.event("[app-preview] User clicked Start App");
            hqImport('analytix/js/google').track.event("App Preview", "User clicked Start App");
            FormplayerFrontend.trigger("app:select", this.appId);
        },
    });

    LandingPageAppView = Marionette.LayoutView.extend({
        template: "#landing-page-app-template",
        className: 'landing-page-app-view',

        events: _.extend({
            'click .js-start-app': 'startApp',
        }, BaseAppView.events),
        incompleteSessionsClick: _.extend(BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(BaseAppView.syncClick),
        onClickRestoreAs: _.extend(BaseAppView.onClickRestoreAs),
        onClickSettings: _.extend(BaseAppView.onClickSettings),

        initialize: function (options) {
            this.appId = options.appId;
        },
        templateHelpers: function () {
            var currentApp = FormplayerFrontend.request("appselect:getApp", this.appId),
                appName = currentApp.get('name'),
                imageUri = currentApp.get('imageUri');
            return {
                appName: appName,
                imageUrl: imageUri && this.appId ? FormplayerFrontend.request('resourceMap', imageUri, this.appId) : "",
            };
        },
        startApp: function () {
            FormplayerFrontend.trigger("app:select", this.appId);
        },
    });

    return {
        GridView: function(options) {
            return new GridView(options);
        },
        SingleAppView: function (options) {
            return new SingleAppView(options);
        },
        LandingPageAppView: function (options) {
            return new LandingPageAppView(options);
        },
    };
});
