/* globals _, $, Array, window */
/**
 *  Handles communication with the google analytics API. gtag is the replacement
 *  for Google's old analytics.js (ga).
 */
hqDefine('analytics/js/google', function () {
    'use strict';
    var _get = hqImport('analytics/js/initial').getFn('google'),
        logger = hqImport('analytics/js/logging').getLoggerForApi('Google Analytics'),
        _utils = hqImport('analytics/js/utils'),
        _init = {},
        _gtag;

    logger.verbose.addCategory('data', 'DATA');

    _init.apiId = _get('apiId');
    logger.verbose.data(_init.apiId || "NOT SET", "API ID");

    var _addGoogleScript = function (srcUrl) {
        logger.verbose.log(srcUrl, "Added Script");
        _utils.insertAsyncScript(srcUrl);
    };

    if (_init.apiId) {
        _addGoogleScript('//www.googletagmanager.com/gtag/js?id=' + _init.apiId);
    }

    window.dataLayer = window.dataLayer || [];
    _gtag = function () {
        window.dataLayer.push(arguments);
        logger.verbose.log(arguments, 'gtag');
    };
    _gtag('js', new Date());

    _init.user = {
        user_id: _get('userId', 'none'),
        isDimagi: _get('userIsDimagi', 'no', 'yes'),
        isCommCare: _get('userIsCommCare', 'no', 'yes'),
        domain: _get('domain', 'none'),
        hasBuiltApp: _get('userHasBuiltApp', 'no', 'yes'),
    };
    // Update User Data & Legacy "Dimensions"
    _init.dimLabels = ['isDimagi', 'user_id', 'isCommCare', 'domain', 'hasBuiltApp'];
    if (_init.user.user_id !== 'none') {
        _init.user.daysOld = _get('userDaysSinceCreated');
        _init.user.isFirstDay = _init.user.daysOld < 1 ? 'yes' : 'no';
        _init.dimLabels.push('isFirstDay');
        _init.user.isFirstWeek = _init.user.daysOld >= 1 && _init.user.daysOld < 7 ? 'yes' : 'no';
        _init.dimLabels.push('isFirstWeek');
    }
    // Legacy Dimensions
    _init.user.custom_map = {};
    _.each(_init.dimLabels, function (val, ind) {
        _init.user.custom_map['dimension' + ind] = _init.user[val];
    });

    // Configure Gtag with User Info
    _gtag('config', _init.apiId, _init.user);

    /**
     * Helper function for sending a Google Analytics Event.
     *
     * @param {string} eventCategory - The event category
     * @param {string} eventAction - The event action
     * @param {string} eventLabel - (optional) The event label
     * @param {string} eventValue - (optional) The event value
     * @param {object} eventParameters - (optional) Extra event parameters
     * @param {function} eventCallback - (optional) Event callback fn
     */
    var trackEvent = function (eventCategory, eventAction, eventLabel, eventValue, eventParameters, eventCallback) {
        var params = {
            event_category: eventCategory,
            event_label: eventLabel,
            event_value: eventValue,
            event_callback: eventCallback,
            event_action: eventAction,
        };
        if (_.isObject(eventParameters)) {
            params = _.extend(params, eventParameters);
        }
        logger.debug.log(logger.fmt.labelArgs(["Category", "Action", "Label", "Value", "Parameters", "Callback"], arguments), "Event Recorded");
        _gtag('event', eventAction, params);
    };

    /**
     * Tracks an event when the given element is clicked.
     * Uses a callback to ensure that the request to the analytics services
     * completes before the default click action happens. This is useful if
     * the link would otherwise navigate away from the page.
     * @param {(object|string)} element - The element (or a selector) whose clicks you want to track.
     * @param {string} eventCategory - The event category
     * @param {string} eventAction - The event action
     * @param {string} eventLabel - (optional) The event label
     * @param {string} eventValue - (optional) The event value
     * @param {object} eventParameters - (optional) Extra event parameters
     */
    var trackClick = function (element, eventCategory, eventAction, eventLabel, eventValue, eventParameters) {
        _utils.trackClickHelper(
            element,
            function (callbackFn) {
                trackEvent(eventCategory, eventAction, eventLabel, eventValue, eventParameters, callbackFn);
            }
        );
        logger.debug.log(logger.fmt.labelArgs(["Element", "Category", "Action", "Label", "Value", "Parameters"], arguments), "Added Click Tracker");
    };

    /**
     * Helper function that pre-fills the eventCategory field for all the
     * tracking helper functions. Useful if you want to track a lot of items
     * in a particular area of the site.
     * e.g. "Report Builder" would be the category
     *
     * @param {string} eventCategory - The event category
     */
    var trackCategory = function (eventCategory) {
        return {
            /**
             * @param {string} eventAction - The event action
             * @param {string} eventLabel - (optional) The event label
             * @param {string} eventValue - (optional) The event value
             * @param {object} eventParameters - (optional) Extra event parameters
             * @param {function} eventCallback - (optional) Event callback fn
             */
            event: function (eventAction, eventLabel, eventValue, eventParameters, eventCallback) {
                trackEvent.apply(null, _.union([eventCategory], Array.from(arguments)));
            },
            /**
             * @param {(object|string)} element - The element (or a selector) whose clicks you want to track.
             * @param {string} eventAction - The event action
             * @param {string} eventLabel - (optional) The event label
             * @param {string} eventValue - (optional) The event value
             * @param {object} eventParameters - (optional) Extra event parameters
             */
            click: function (element, eventAction, eventLabel, eventValue, eventParameters) {
                trackClick.apply(null, _.union([arguments[0], eventCategory], Array.from(arguments).splice(1)));
            },
        };
    };

    return {
        logger: logger,
        track: {
            event: trackEvent,
            click: trackClick,
        },
        trackCategory: trackCategory,
    };
});
