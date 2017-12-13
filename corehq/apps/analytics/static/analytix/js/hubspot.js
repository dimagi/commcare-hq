/* globals window */
/**
 * Instatiates the Hubspot analytics platform.
 */
hqDefine('analytix/js/hubspot', [
    'underscore',
    'analytix/js/initial',
    'analytix/js/logging',
    'analytix/js/utils',
], function (
    _,
    initialAnalytics,
    logging,
    utils
) {
    'use strict';
    var _get = initialAnalytics.getFn('hubspot'),
        _global = initialAnalytics.getFn('global'),
        _data = {},
        logger = logging.getLoggerForApi('Hubspot');

    var _hsq = window._hsq = window._hsq || [];

    var __init__ = function () {
        logger = logging.getLoggerForApi('Hubspot');
        _data.apiId = _get('apiId');
        if (_data.apiId) {
            _data.scriptSrc = '//js.hs-analytics.net/analytics/' + utils.getDateHash() + '/' + _data.apiId + '.js';
            utils.insertScript(_data.scriptSrc, logger.debug.log, {
                id: 'hs-analytics',
            });
        }
    };

    $(function() {
        if (_global('isEnabled')) {
            __init__();
            logger.debug.log('Initialized');
        }
    });

    /**
     * Sends data to Hubspot to identify the current session.
     * @param {object} data
     */
    var identify = function (data) {
        logger.debug.log(data, "Identify");
        _hsq.push(['identify', data]);
    };

    /**
     * Tracks an event through the Hubspot API
     * @param {string} eventId - The ID of the event. If you created the event in HubSpot, use the numerical ID of the event.
     * @param {integer|float} value - This is an optional argument that can be used to track the revenue of an event.
     */
    var trackEvent = function (eventId, value) {
        if (_global('isEnabled')) {
            logger.debug.log(logger.fmt.labelArgs(["Event ID", "Value"], arguments), 'Track Event');
            _hsq.push(['trackEvent', {
                id: eventId,
                value: value,
            }]);
        }
    };

    return {
        logger: logger,
        identify: identify,
        trackEvent: trackEvent,
    };
});
