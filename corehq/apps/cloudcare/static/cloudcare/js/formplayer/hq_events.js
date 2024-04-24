'use strict';
/**
 * hq_events.js
 *
 * This is framework for allowing messages from HQ
 */
hqDefine("cloudcare/js/formplayer/hq_events", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");
    var self = {};

    self.Receiver = function (allowedHost) {
        this.allowedHost = allowedHost;
        return receiver.bind(this);
    };

    var receiver = function (event) {
        // For Chrome, the origin property is in the event.originalEvent object
        var origin = event.origin || event.originalEvent.origin,
            data = event.data,
            appId;

        if (!origin.endsWith(this.allowedHost)) {
            window.console.warn('Disallowed origin ' + origin);
            return;
        }

        if (!_.has(data, 'action')) {
            window.console.warn('Message must have action property');
            return;
        }
        if (!_.contains(_.values(self.Actions), data.action)) {
            window.console.warn('Invalid action ' + data.action);
            return;
        }

        switch (data.action) {
            case self.Actions.TABLET_VIEW:
                FormplayerFrontend.trigger('view:tablet');
                break;
            case self.Actions.PHONE_VIEW:
                FormplayerFrontend.trigger('view:phone');
                break;
            case self.Actions.BACK:
                FormplayerFrontend.trigger('navigation:back');
                break;
            case self.Actions.REFRESH:
                appId = FormplayerFrontend.getChannel().request('getCurrentAppId');
                FormplayerFrontend.trigger('refreshApplication', appId);
                break;
        }
    };

    self.Actions = {
        BACK: 'back',
        REFRESH: 'refresh',
        PHONE_VIEW: 'phone-view',
        TABLET_VIEW: 'tablet-view',
    };

    return self;
});
