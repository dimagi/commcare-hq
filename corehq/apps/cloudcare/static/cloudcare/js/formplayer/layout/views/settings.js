/*global _, FormplayerFrontend, Util, Marionette */

hqDefine("cloudcare/js/formplayer/layout/views/settings", function () {
    var slugs = {
        SET_LANG: 'lang',
        SET_DISPLAY: 'display',
        CLEAR_USER_DATA: 'clear-user-data',
        BREAK_LOCKS: 'break-locks',
    };

    /**
     * Sets the application language. Should only be used for App Preview.
     */
    var LangSettingView = Marionette.View.extend({
        template: _.template($("#lang-setting-template").html() || ""),
        tagName: 'tr',
        initialize: function () {
            this.currentUser = FormplayerFrontend.getChannel().request('currentUser');
        },
        ui: {
            language: '.js-lang',
        },
        events: {
            'change @ui.language': 'onLanguageChange',
        },
        onLanguageChange: function (e) {
            this.currentUser.displayOptions.language = $(e.currentTarget).val();
            Util.saveDisplayOptions(this.currentUser.displayOptions);
        },
        templateContext: function () {
            var appId = FormplayerFrontend.getChannel().request('getCurrentAppId');
            var currentApp = FormplayerFrontend.getChannel().request("appselect:getApp", appId);
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
            this.currentUser = FormplayerFrontend.getChannel().request('currentUser');
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
            Util.saveDisplayOptions(this.currentUser.displayOptions);
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

    var SettingsContainerView = Marionette.CollectionView.extend({
        tagName: 'tbody',
        childView: function (item) {
            if (item.get('slug') === slugs.SET_LANG) {
                return LangSettingView;
            } else if (item.get('slug') === slugs.SET_DISPLAY) {
                return DisplaySettingView;
            } else if (item.get('slug') === slugs.CLEAR_USER_DATA) {
                return ClearUserDataView;
            } else if (item.get('slug') === slugs.BREAK_LOCKS) {
                return BreakLocksView;
            }
        },
    });

    var SettingsView = Marionette.View.extend({
        regions: {
            body: {
                el: 'table',
            },
        },
        onRender: function () {
            this.showChildView('body', new SettingsContainerView({
                collection: this.collection,
            }));
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
