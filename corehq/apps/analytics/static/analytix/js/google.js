"use strict";
/**
 *  Handles communication with the google analytics API. gtag is the replacement
 *  for Google's old analytics.js (ga).
 */
hqDefine('analytix/js/google', [
    'jquery',
    'underscore',
    'analytix/js/initial',
    'analytix/js/logging',
    'analytix/js/utils',
], function (
    $,
    _,
    initialAnalytics,
    logging,
    utils
) {
    var _get = initialAnalytics.getFn('google'),
        _logger = logging.getLoggerForApi('Google Analytics'),
        _ready = $.Deferred();

    var _gtag = function () {
        // This should never run, because all calls to _gtag should be
        // inside done handlers for ready, but just in case...
        _logger.warning.log(arguments, 'skipped gtag');
    };

    $(function () {
        var apiId = _get('apiId'),
            scriptUrl = '//www.googletagmanager.com/gtag/js?id=' + apiId;

        _logger = logging.getLoggerForApi('Google Analytics');
        _ready = utils.initApi(_ready, apiId, scriptUrl, _logger, function () {
            window.dataLayer = window.dataLayer || [];
            _gtag = function () {
                window.dataLayer.push(arguments);
                _logger.verbose.log(arguments, 'gtag');
            };
            _gtag('js', new Date());

            var config = {
                user_id: _get('userId', 'none'),
                isDimagi: _get('userIsDimagi', 'no', 'yes'),
                isCommCare: _get('userIsCommCare', 'no', 'yes'),
                domain: _get('domain', 'none'),
                hasBuiltApp: _get('userHasBuiltApp', 'no', 'yes'),
                linker: {
                    accept_incoming: true,  // this is necessary for cross-domain tracking with dimagi.com
                    domains: ['dimagi.com'],
                },
            };

            // Update User Data & Legacy "Dimensions"
            var dimLabels = ['isDimagi', 'user_id', 'isCommCare', 'domain', 'hasBuiltApp'];
            if (config.user_id !== 'none') {
                config.daysOld = _get('userDaysSinceCreated');
                config.isFirstDay = config.daysOld < 1 ? 'yes' : 'no';
                dimLabels.push('isFirstDay');
                config.isFirstWeek = config.daysOld >= 1 && config.daysOld < 7 ? 'yes' : 'no';
                dimLabels.push('isFirstWeek');
            }
            // Legacy Dimensions
            config.custom_map = {};
            _.each(dimLabels, function (val, ind) {
                config.custom_map['dimension' + ind] = config[val];
            });

            // Configure Gtag
            _gtag('config', apiId, config);
        });
    });

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
        var originalArgs = arguments;
        _ready.done(function () {
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
            _logger.debug.log(_logger.fmt.labelArgs(["Category", "Action", "Label", "Value", "Parameters", "Callback"], originalArgs), "Event Recorded");
            _gtag('event', eventAction, params);
        }).fail(function () {
            if (_.isFunction(eventCallback)) {
                eventCallback();
            }
        });
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
        var originalArgs = arguments;
        _ready.done(function () {
            utils.trackClickHelper(
                element,
                function (callbackFn) {
                    trackEvent(eventCategory, eventAction, eventLabel, eventValue, eventParameters, callbackFn);
                }
            );
            _logger.debug.log(_logger.fmt.labelArgs(["Element", "Category", "Action", "Label", "Value", "Parameters"], originalArgs), "Added Click Tracker");
        });
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
                trackEvent(eventCategory, eventAction, eventLabel, eventValue, eventParameters, eventCallback);
            },
            /**
             * @param {(object|string)} element - The element (or a selector) whose clicks you want to track.
             * @param {string} eventAction - The event action
             * @param {string} eventLabel - (optional) The event label
             * @param {string} eventValue - (optional) The event value
             * @param {object} eventParameters - (optional) Extra event parameters
             */
            click: function (element, eventAction, eventLabel, eventValue, eventParameters) {
                // directly reference what the module returns instead of the private function,
                // as some mocha tests will want to replace the module's returned functions
                trackClick(element, eventCategory, eventLabel, eventValue, eventParameters);
            },
        };
    };

    return {
        track: {
            event: trackEvent,
            click: trackClick,
        },
        trackCategory: trackCategory,
    };
});
