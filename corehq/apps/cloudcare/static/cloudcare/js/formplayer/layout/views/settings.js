'use strict';
hqDefine("cloudcare/js/formplayer/layout/views/settings", [
    'jquery',
    'underscore',
    'backbone.marionette',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/apps/api',
    'cloudcare/js/formplayer/users/models',
    'cloudcare/js/formplayer/utils/utils',
    'bootstrap-switch/dist/js/bootstrap-switch', // bootstrapSwitch
], function (
    $,
    _,
    Marionette,
    FormplayerFrontend,
    AppsAPI,
    UsersModels,
    Utils
) {
    var slugs = {
        SET_LANG: 'lang',
        SET_DISPLAY: 'display',
        CLEAR_USER_DATA: 'clear-user-data',
        BREAK_LOCKS: 'break-locks',
        SYNC: 'sync',
    };

    /**
     * Sets the application language. Should only be used for App Preview.
     */
    var LangSettingView = Marionette.View.extend({
        template: _.template($("#lang-setting-template").html() || ""),
        tagName: 'tr',
        initialize: function () {
            this.currentUser = UsersModels.getCurrentUser();
        },
        ui: {
            language: '.js-lang',
        },
        events: {
            'change @ui.language': 'onLanguageChange',
        },
        onLanguageChange: function (e) {
            this.currentUser.displayOptions.language = $(e.currentTarget).val();
            Utils.saveDisplayOptions(this.currentUser.displayOptions);
        },
        templateContext: function () {
            var appId = FormplayerFrontend.getChannel().request('getCurrentAppId');
            var currentApp = AppsAPI.getAppEntity(appId);
            return {
                langs: currentApp.get('langs'),
                currentLang: this.currentUser.displayOptions.language,
            };
        },
    });

    /**
     * Sets whether or not the application should use One Question Per Screen or not.
     * Should only be used for App Preview.
     */
    var DisplaySettingView = Marionette.View.extend({
        template: _.template($("#display-setting-template").html() || ""),
        tagName: 'tr',
        initialize: function () {
            this.currentUser = UsersModels.getCurrentUser();
        },
        ui: {
            oneQuestionPerScreen: '.js-one-question-per-screen',
        },
        events: {
            'switchChange.bootstrapSwitch @ui.oneQuestionPerScreen': 'onChangeOneQuestionPerScreen',
        },
        onRender: function () {
            this.ui.oneQuestionPerScreen.bootstrapSwitch(
                'state',
                this.currentUser.displayOptions.oneQuestionPerScreen
            );
        },
        onChangeOneQuestionPerScreen: function (e, switchValue) {
            this.currentUser.displayOptions.oneQuestionPerScreen = switchValue;
            Utils.saveDisplayOptions(this.currentUser.displayOptions);
        },
    });

    /**
     * Force clear user data.
     * Available for both Web Apps and App Preview
     */
    var ClearUserDataView = Marionette.View.extend({
        template: _.template($("#clear-user-data-setting-template").html() || ""),
        tagName: 'tr',
        ui: {
            clearUserData: '.js-clear-user-data',
        },
        events: {
            'click @ui.clearUserData': 'onClickClearUserData',
        },
        onClickClearUserData: function (e) {
            var promise = FormplayerFrontend.getChannel().request('clearUserData');
            $(e.currentTarget).prop('disabled', true);
            promise.done(function () {
                $(e.currentTarget).prop('disabled', false);
            });
        },
    });

    /**
     * Break exising locks
     * Available only for Web Apps
     */
    var BreakLocksView = Marionette.View.extend({
        template: _.template($("#break-locks-setting-template").html() || ""),
        tagName: 'tr',
        ui: {
            breakLocks: '.js-break-locks',
        },
        events: {
            'click @ui.breakLocks': 'onClickBreakLocks',
        },
        onClickBreakLocks: function (e) {
            var promise = FormplayerFrontend.getChannel().request('breakLocks');
            $(e.currentTarget).prop('disabled', true);
            promise.done(function () {
                $(e.currentTarget).prop('disabled', false);
            });
        },
    });

    /**
     * Sync button
     * The feature flag HIDE_SYNC_BUTTON moves the sync button here
     */
    var SyncView = Marionette.View.extend({
        template: _.template($("#sync-setting-template").html() || ""),
        tagName: 'tr',
        ui: {
            sync: '.js-sync',
        },
        events: {
            'click @ui.sync': 'onClickSync',
        },
        onClickSync: function (e) {
            FormplayerFrontend.trigger('sync');
            $(e.currentTarget).prop('disabled', true);
        },
    });

    var SettingsView = Marionette.CollectionView.extend({
        childViewContainer: 'tbody',
        childView: function (item) {
            if (item.get('slug') === slugs.SET_LANG) {
                return LangSettingView;
            } else if (item.get('slug') === slugs.SET_DISPLAY) {
                return DisplaySettingView;
            } else if (item.get('slug') === slugs.CLEAR_USER_DATA) {
                return ClearUserDataView;
            } else if (item.get('slug') === slugs.BREAK_LOCKS) {
                return BreakLocksView;
            } else if (item.get('slug') === slugs.SYNC) {
                return SyncView;
            }
        },
        ui: {
            done: '.js-done',
        },
        events: {
            'click @ui.done': 'onClickDone',
        },
        template: _.template($("#settings-template").html() || ""),
        onClickDone: function () {
            FormplayerFrontend.trigger('navigateHome');
        },
    });

    return {
        slugs: slugs,
        SettingsView: function (options) {
            return new SettingsView(options);
        },
    };
});
