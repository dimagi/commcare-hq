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
        ui: {
            backButton: '.formplayer-back',
            reloadButton: '.formplayer-reload',
        },
        events: {
            'click @ui.backButton': 'onBack',
            'click @ui.reloadButton': 'onReload',
        },
        initialize: function(options) {
            this.appId = options.appId;
        },
        onBack: function(e) {
            e.preventDefault();
            window.history.back();
        },
        onReload: function(e) {
            e.preventDefault();
            FormplayerFrontend.trigger('refreshApplication', this.appId);
        },
        hideBackButton: function() {
            this.ui.backButton.hide();
        },
        showBackButton: function() {
            this.ui.backButton.show();
        },
    });
});
