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
            throw new Error('Disallowed origin ' + origin);
        }

        if (!data.hasOwnProperty('action')) {
            throw new Error('Message must have action property');
        }
        if (!_.contains(_.values(Events.Actions), data.action)) {
            throw new Error('Invalid action ' + data.action);
        }

        switch (data.action) {
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
    };
});
