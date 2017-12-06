/* globals Array, window */
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
    'use strict';
    var _get = initialAnalytics.getFn('google'),
        _global = initialAnalytics.getFn('global'),
        logger = undefined,
        _data = {},
        module = {},
        _gtag = function () {},
        _ready = $.Deferred();

    var __init__ = function () {
        logger = logging.getLoggerForApi('Google Analytics');
        _data.apiId = _get('apiId');
        logger.verbose.log(_data.apiId || "NOT SET",["DATA", "API ID"]);

        if (!_data.apiId || !_global('isEnabled')) {
            logger.debug.log("Failed TODO");
            _ready.reject();
            return;
        }

        _data.scriptUrl = '//www.googletagmanager.com/gtag/js?id=' + _data.apiId;
        $.getScript(_data.scriptUrl)
            .done(function() {
                window.dataLayer = window.dataLayer || [];
                _gtag = function () {
                    window.dataLayer.push(arguments);
                    logger.verbose.log(arguments, 'gtag');
                };
                _gtag('js', new Date());

                _data.user = {
                    user_id: _get('userId', 'none'),
                    isDimagi: _get('userIsDimagi', 'no', 'yes'),
                    isCommCare: _get('userIsCommCare', 'no', 'yes'),
                    domain: _get('domain', 'none'),
                    hasBuiltApp: _get('userHasBuiltApp', 'no', 'yes'),
                };

                // Update User Data & Legacy "Dimensions"
                _data.dimLabels = ['isDimagi', 'user_id', 'isCommCare', 'domain', 'hasBuiltApp'];
                if (_data.user.user_id !== 'none') {
                    _data.user.daysOld = _get('userDaysSinceCreated');
                    _data.user.isFirstDay = _data.user.daysOld < 1 ? 'yes' : 'no';
                    _data.dimLabels.push('isFirstDay');
                    _data.user.isFirstWeek = _data.user.daysOld >= 1 && _data.user.daysOld < 7 ? 'yes' : 'no';
                    _data.dimLabels.push('isFirstWeek');
                }
                // Legacy Dimensions
                _data.user.custom_map = {};
                _.each(_data.dimLabels, function (val, ind) {
                    _data.user.custom_map['dimension' + ind] = _data.user[val];
                });

                // Configure Gtag with User Info
                _gtag('config', _data.apiId, _data.user);
                _ready.resove();

                logger.debug.log('Initialized');
            })
            .fail(function() {
                logger.debug.log(_data.scriptUrl, "Failed to Load Script - Check Adblocker");
                _ready.reject();
            });
    };

    $(function() {
        __init__();
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
        _ready.done(function() {
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
        }).fail(function() {
            eventCallback();
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
        _ready.done(function() {
            utils.trackClickHelper(
                element,
                function (callbackFn) {
                    trackEvent(eventCategory, eventAction, eventLabel, eventValue, eventParameters, callbackFn);
                }
            );
            logger.debug.log(logger.fmt.labelArgs(["Element", "Category", "Action", "Label", "Value", "Parameters"], arguments), "Added Click Tracker");
        });
    };


    module = {
        logger: logger,
        track: {
            event: trackEvent,
            click: trackClick,
        },
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
                module.track.event(eventCategory, eventAction, eventLabel, eventValue, eventParameters, eventCallback);
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
                module.track.click(element, eventCategory, eventLabel, eventValue, eventParameters);
            },
        };
    };

    module.trackCategory = trackCategory;
    return module;
});
