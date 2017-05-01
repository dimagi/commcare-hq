/*global FormplayerFrontend, Util */

FormplayerFrontend.module("Layout.Views", function (Views, FormplayerFrontend, Backbone, Marionette) {
    Views.SettingsView = Marionette.ItemView.extend({
        ui: {
            oneQuestionPerScreen: '.js-one-question-per-screen',
            language: '.js-lang',
            done: '.js-done',
        },
        events: {
            'switchChange.bootstrapSwitch @ui.oneQuestionPerScreen': 'onChangeOneQuestionPerScreen',
            'change @ui.language': 'onLanguageChange',
            'click @ui.done': 'onClickDone',
        },
        template: '#settings-template',
        initialize: function() {
            this.currentUser = FormplayerFrontend.request('currentUser');
        },
        templateHelpers: function() {
            var appId = FormplayerFrontend.request('getCurrentAppId');
            var currentApp = FormplayerFrontend.request("appselect:getApp", appId);
            return {
                langs: currentApp.get('langs'),
                displayOptions: this.currentUser.displayOptions,
            };
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
        onLanguageChange: function(e) {
            this.currentUser.displayOptions.language = $(e.currentTarget).val();
            Util.saveDisplayOptions(this.currentUser.displayOptions);
        },
        onClickDone: function() {
            FormplayerFrontend.trigger('navigateHome');
        },
    });
});
