/*global FormplayerFrontend, Util */

FormplayerFrontend.module("SessionNavigate.AppList", function (AppList, FormplayerFrontend, Backbone, Marionette) {
    AppList.SettingsView = Marionette.ItemView.extend({
        ui: {
            oneQuestionPerScreen: '.js-one-question-per-screen',
            done: '.js-done',
        },
        events: {
            'switchChange.bootstrapSwitch @ui.oneQuestionPerScreen': 'onChangeOneQuestionPerScreen',
            'click @ui.done': 'onClickDone',
        },
        template: '#settings-template',
        initialize: function() {
            this.currentUser = FormplayerFrontend.request('currentUser');
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
        onClickDone: function() {
            FormplayerFrontend.trigger('navigateHome');
        },
    });
});
