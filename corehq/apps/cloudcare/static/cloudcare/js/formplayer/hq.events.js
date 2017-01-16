/*global FormplayerFrontend */

/**
 * hq.events.js
 *
 * This is framework for allowing messages from HQ
 */
FormplayerFrontend.module("HQ.Events", function(Events, FormplayerFrontend) {

    Events.Receiver = function(allowedHost) {
        this.allowedHost = allowedHost;
        return receiver.bind(this);
    };

    var receiver = function(event) {
        // For Chrome, the origin property is in the event.originalEvent object
        var origin = event.origin || event.originalEvent.origin,
            data = event.data,
            appId;

        if (!origin.endsWith(this.allowedHost)) {
            window.console.warn('Disallowed origin ' + origin);
            return;
        }

        if (!data.hasOwnProperty('action')) {
            window.console.warn('Message must have action property');
            return;
        }
        if (!_.contains(_.values(Events.Actions), data.action)) {
            window.console.warn('Invalid action ' + data.action);
            return;
        }

        switch (data.action) {
        case Events.Actions.TABLET_VIEW:
            FormplayerFrontend.trigger('view:tablet');
            break;
        case Events.Actions.PHONE_VIEW:
            FormplayerFrontend.trigger('view:phone');
            break;
        case Events.Actions.BACK:
            FormplayerFrontend.trigger('navigation:back');
            break;
        case Events.Actions.REFRESH:
            appId = FormplayerFrontend.request('getCurrentAppId');
            FormplayerFrontend.trigger('refreshApplication', appId);
            break;
        }
    };

    Events.Actions = {
        BACK: 'back',
        REFRESH: 'refresh',
        PHONE_VIEW: 'phone-view',
        TABLET_VIEW: 'tablet-view',
    };
});
