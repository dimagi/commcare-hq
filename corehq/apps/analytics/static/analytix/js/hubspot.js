/* globals _, window */
/**
 * Instatiates the Hubspot analytics platform.
 */
hqDefine('analytix/js/hubspot', function () {
    'use strict';
    var _get = hqImport('analytix/js/initial').getFn('hubspot'),
        _global = hqImport('analytix/js/initial').getFn('global'),
        logger = hqImport('analytix/js/logging').getLoggerForApi('Hubspot'),
        _utils = hqImport('analytix/js/utils'),
        _data = {};

    var _hsq = window._hsq = window._hsq || [];

    var __init__ = function () {
        _data.apiId = _get('apiId');
        if (_data.apiId) {
            _data.scriptSrc = '//js.hs-analytics.net/analytics/' + _utils.getDateHash() + '/' + _data.apiId;
            _utils.insertScript(_data.scriptSrc, logger.debug.log, {
                id: 'hs-analytics',
            });
        }
    };
    if (_global('isEnabled')) {
        __init__();
        logger.debug.log('Initialized');
    }

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
