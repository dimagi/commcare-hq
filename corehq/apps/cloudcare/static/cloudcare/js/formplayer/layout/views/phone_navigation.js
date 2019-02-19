/* globals FormplayerFrontend */
FormplayerFrontend.module("Layout.Views", function (Views, FormplayerFrontend, Backbone, Marionette) {
    /**
     * PhoneNavigation
     *
     * This view controls the navigation we use when in phone mode. This will
     * allow a user to click buttons such as back and are omnipresent throughout
     * the session.
     */
    Views.PhoneNavigation = Marionette.ItemView.extend({
        className: 'formplayer-phone-navigation',
        template: '#formplayer-phone-navigation-template',
        initialize: function (options) {
            this.appId = options.appId;
        },
    });
});
