/*global FormplayerFrontend, Util */

FormplayerFrontend.module("Layout.Views", function (Views, FormplayerFrontend, Backbone, Marionette) {
    /**
     * Sets the application language. Should only be used for App Preview.
     */
    var LangSettingView = Marionette.ItemView.extend({
        template: '#lang-setting-template',
        tagName: 'tr',
        initialize: function() {
            this.currentUser = FormplayerFrontend.request('currentUser');
        },
        ui: {
            language: '.js-lang',
        },
        events: {
            'change @ui.language': 'onLanguageChange',
        },
        onLanguageChange: function(e) {
            this.currentUser.displayOptions.language = $(e.currentTarget).val();
            Util.saveDisplayOptions(this.currentUser.displayOptions);
        },
        templateHelpers: function() {
            var appId = FormplayerFrontend.request('getCurrentAppId');
            var currentApp = FormplayerFrontend.request("appselect:getApp", appId);
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
    var DisplaySettingView = Marionette.ItemView.extend({
        template: '#display-setting-template',
        tagName: 'tr',
        initialize: function() {
            this.currentUser = FormplayerFrontend.request('currentUser');
        },
        ui: {
            oneQuestionPerScreen: '.js-one-question-per-screen',
        },
        events: {
            'switchChange.bootstrapSwitch @ui.oneQuestionPerScreen': 'onChangeOneQuestionPerScreen',
        },
        onRender: function() {
            this.ui.oneQuestionPerScreen.bootstrapSwitch(
                'state',
                this.currentUser.displayOptions.oneQuestionPerScreen
            );
        },
        onChangeOneQuestionPerScreen: function(e, switchValue) {
            this.currentUser.displayOptions.oneQuestionPerScreen = switchValue;
            Util.saveDisplayOptions(this.currentUser.displayOptions);
        },
    });

    Views.SettingsView = Marionette.CompositeView.extend({
        ui: {
            done: '.js-done',
        },
        childViewContainer: 'tbody',
        getChildView: function(item) {
            if (item.get('slug') === Views.SettingSlugs.SET_LANG) {
                return LangSettingView;
            } else if (item.get('slug') === Views.SettingSlugs.SET_DISPLAY) {
                return DisplaySettingView;
            }
        },
        events: {
            'click @ui.done': 'onClickDone',
        },
        template: '#settings-template',
        onClickDone: function() {
            FormplayerFrontend.trigger('navigateHome');
        },
    });

    Views.SettingSlugs = {
        SET_LANG: 'lang',
        SET_DISPLAY: 'display',
    };

});
