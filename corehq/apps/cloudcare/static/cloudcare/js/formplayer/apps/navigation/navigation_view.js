/* globals FormplayerFrontend */
FormplayerFrontend.module("Navigation", function (Navigation, FormplayerFrontend, Backbone, Marionette) {
    /**
     * PhoneNavigation
     *
     * This view controls the navigation we use when in phone mode. This will
     * allow a user to click buttons such as back and are omnipresent throughout
     * the session.
     */
    Navigation.PhoneNavigation = Marionette.ItemView.extend({
        className: 'formplayer-phone-navigation',
        template: '#formplayer-phone-navigation-template',
        events: {
            'click .js-formplayer-back': 'onBack',
            'click .js-formplayer-reload': 'onReload',
            'click .js-formplayer-clear-user-data': 'onClearUserData',
        },
        initialize: function(options) {
            this.appId = options.appId;
        },
        onBack: function(e) {
            e.preventDefault();
            window.history.back();
        },
        onClearUserData: function(e) {
            e.preventDefault();
            FormplayerFrontend.trigger('clearUserData', this.appId);
        },
        onReload: function(e) {
            e.preventDefault();
            FormplayerFrontend.trigger('refreshApplication', this.appId);
        },
    });
});
