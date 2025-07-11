define("cloudcare/js/formplayer/apps/views", [
    'jquery',
    'underscore',
    'backbone.marionette',
    'analytix/js/google',
    'analytix/js/noopMetrics',
    'cloudcare/js/formplayer/constants',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/apps/api',
], function (
    $,
    _,
    Marionette,
    googleAnalytics,
    noopMetrics,
    constants,
    FormplayerFrontend,
    AppsAPI,
) {
    var GridItem = Marionette.View.extend({
        template: _.template($("#row-template").html() || ""),
        tagName: "div",
        className: "grid-item col-sm-6 col-md-4 col-xl-3 formplayer-request",
        events: {
            "click": "rowClick",
            "keydown": "rowKeyAction",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("app:select", this.model.get('copy_of'));
        },

        rowKeyAction: function (e) {
            if (e.keyCode === 13) {
                // Select application on Enter keydown event.
                this.rowClick(e);
            }
        },

        templateContext: function () {
            var imageUri = this.options.model.get('imageUri');
            var appId = this.options.model.get('_id');
            return {
                imageUrl: imageUri && appId ? FormplayerFrontend.getChannel().request('resourceMap', imageUri, appId) : "",
            };
        },
    });

    var BaseAppView = {
        events: {
            'click .js-incomplete-sessions-item': 'incompleteSessionsClick',
            'click .js-sync-item': 'syncClick',
            'click .js-restore-as-item': 'onClickRestoreAs',
            'click .js-settings': 'onClickSettings',
            'keydown .js-incomplete-sessions-item': 'incompleteSessionsKeyAction',
            'keydown .js-sync-item': 'syncKeyAction',
            'keydown .js-restore-as-item': 'restoreAsKeyAction',
            'keydown .js-settings': 'settingsKeyAction',
        },
        incompleteSessionsClick: function (e) {
            e.preventDefault();
            var pageSize = constants.DEFAULT_INCOMPLETE_FORMS_PAGE_SIZE;
            FormplayerFrontend.trigger("sessions", 0, pageSize);
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
        incompleteSessionsKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.incompleteSessionsClick(e);
            }
        },
        syncKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.syncClick(e);
            }
        },
        restoreAsKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.onClickRestoreAs(e);
            }
        },
        settingsKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.onClickSettings(e);
            }
        },
    };

    var GridView = Marionette.CollectionView.extend({
        template: _.template($("#grid-template").html() || ""),
        childView: GridItem,
        childViewContainer: ".row",
        events: _.extend(BaseAppView.events),
        incompleteSessionsClick: _.extend(BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(BaseAppView.syncClick),
        onClickRestoreAs: _.extend(BaseAppView.onClickRestoreAs),
        onClickSettings: _.extend(BaseAppView.onClickSettings),
        incompleteSessionsKeyAction: _.extend(BaseAppView.incompleteSessionsKeyAction),
        syncKeyAction: _.extend(BaseAppView.syncKeyAction),
        restoreAsKeyAction: _.extend(BaseAppView.restoreAsKeyAction),
        settingsKeyAction: _.extend(BaseAppView.settingsKeyAction),

        // Cannot append at the end of the parent because there are
        // special grid items.
        attachHtml: function attachHtml(els, $container) {
            let childElement = $container.find("#put-apps-here");
            $container[0].insertBefore(els, childElement[0]);
        },

        initialize: function (options) {
            this.shouldShowIncompleteForms = options.shouldShowIncompleteForms;
            sessionStorage.removeItem('handledDefaultClosed');
            sessionStorage.removeItem('persistantMenuRegionWidth');
            $('#persistent-menu-region').css('width', '');
        },

        templateContext: function () {
            return {
                shouldShowIncompleteForms: this.shouldShowIncompleteForms,
            };
        },
    });

    /**
     * SingleAppView
     *
     * This provides a view for when previewing an application of a known id.
     * The user doesn't need to select the application because we already have
     * that information. Used for phone previewing in the app manager
     */
    var SingleAppView = Marionette.View.extend({
        template: _.template($("#single-app-template").html() || ""),
        className: 'single-app-view',

        events: _.extend({
            'click .js-start-app': 'startApp',
            'keydown .js-start-app': 'keyAction',
        }, BaseAppView.events),
        incompleteSessionsClick: _.extend(BaseAppView.incompleteSessionsClick),
        syncClick: _.extend(BaseAppView.syncClick),
        onClickRestoreAs: _.extend(BaseAppView.onClickRestoreAs),
        onClickSettings: _.extend(BaseAppView.onClickSettings),
        incompleteSessionsKeyAction: _.extend(BaseAppView.incompleteSessionsKeyAction),
        syncKeyAction: _.extend(BaseAppView.syncKeyAction),
        restoreAsKeyAction: _.extend(BaseAppView.restoreAsKeyAction),
        settingsKeyAction: _.extend(BaseAppView.settingsKeyAction),

        initialize: function (options) {
            this.appId = options.appId;
        },
        templateContext: function () {
            var currentApp = AppsAPI.getAppEntity(this.appId),
                appName;
            appName = currentApp.get('name');
            return {
                shouldShowIncompleteForms: function () {
                    return FormplayerFrontend.getChannel()
                        .request('getAppDisplayProperties')['cc-show-incomplete'] === 'yes';
                },
                appName: appName,
            };
        },
        startApp: function (e) {
            e.preventDefault();
            noopMetrics.track.event("[app-preview] User clicked Start App");
            googleAnalytics.track.event("App Preview", "User clicked Start App");
            FormplayerFrontend.trigger("app:select", this.appId);
        },
        keyAction: function (e) {
            if (e.keyCode === 13) {
                this.startApp(e);
            }
        },
    });

    return {
        GridView: function (options) {
            return new GridView(options);
        },
        SingleAppView: function (options) {
            return new SingleAppView(options);
        },
    };
});
