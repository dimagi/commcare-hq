/* globals _kmq */

var _kmq = window._kmq = _kmq || [];

hqDefine('analytix/js/kissmetrix', [
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
    var _get = initialAnalytics.getFn('kissmetrics'),
        _allAbTests = {},
        _logger = logging.getLoggerForApi('Kissmetrics'),
        _ready = $.Deferred();

    window.dataLayer = window.dataLayer || [];

    /**
     * Push data to _kmq by command type.
     * @param {string} commandName
     * @param {object} properties
     * @param {function|undefined} callbackFn - optional
     * @param {string|undefined} eventName - optional
     */
    var _kmqPushCommand = function (commandName, properties, callbackFn, eventName) {
        _ready.done(function () {
            var command, data;
            command = _.compact([commandName, eventName, properties, callbackFn]);
            _kmq.push(command);
            data = {
                event: 'km_' + commandName,
            };
            if (eventName) data.km_event = eventName;
            if (properties) data.km_property = properties;
            window.dataLayer.push(data);
            _logger.verbose.log(command, ['window._kmq.push', 'window.dataLayer.push', '_kmqPushCommand', commandName]);
        }).fail(function () {
            callbackFn();
        });
    };

    $(function () {
        var apiId = _get('apiId'),
            scriptUrls = [
                '//i.kissmetrics.com/i.js',
                '//doug1izaerwt3.cloudfront.net/' + apiId + '.1.js',
            ];

        _logger = logging.getLoggerForApi('Kissmetrics');
        _ready = utils.initApi(_ready, apiId, scriptUrls, _logger, function () {
            // Identify user and HQ instance
            // This needs to happen before any events are sent or any traits are set
            var username = _get('username');
            if (username) {
                identify(username);
                var traits = {
                    'is_dimagi': _get('isDimagi'),
                    'hq_instance': _get('hqInstance'),
                };
                identifyTraits(traits);
            }

            // Initialize Kissmetrics AB Tests
            var abTests = initialAnalytics.getAbTests('kissmetrics');
            _.each(abTests, function (ab, testName) {
                var test = {};
                testName = _.last(testName.split('.'));
                if (_.isObject(ab) && ab.version) {
                    test[ab.name || testName] = ab.version;
                    _logger.debug.log(test, ["AB Test", "New Test: " + testName]);
                    _kmqPushCommand('set', test);
                    _.extend(_allAbTests, test);
                }
            });
        });
    });

    /**
     * Identifies the current user
     * @param {string} identity - A unique ID to identify the session. Typically the user's email address.
     */
    var identify = function (identity) {
        var originalArgs = arguments;
        _ready.done(function () {
            _logger.debug.log(originalArgs, 'Identify');
            _kmqPushCommand('identify', identity);
        });
    };

    /**
     * Sets traits for the current user
     * @param {object} traits - an object of traits
     * @param {function} callbackFn - (optional) callback function
     * @param {integer} timeout - (optional) timeout in milliseconds
     */
    var identifyTraits = function (traits, callbackFn, timeout) {
        var originalArgs = arguments;
        _ready.done(function () {
            _logger.debug.log(_logger.fmt.labelArgs(["Traits", "Callback Function", "Timeout"], originalArgs), 'Identify Traits (Set)');
            callbackFn = utils.createSafeCallback(callbackFn, timeout);
            _kmqPushCommand('set', traits, callbackFn);
        }).fail(function () {
            if (_.isFunction(callbackFn)) {
                callbackFn();
            }
        });
    };

    /**
     * Records an event and its properties
     * @param {string} name - Name of event to be tracked
     * @param {object} properties - (optional) Properties related to the event being tracked
     * @param {function} callbackFn - (optional) Function to be called after the event is tracked.
     * @param {integer} timeout - (optional) Timeout for safe callback
     */
    var trackEvent = function (name, properties, callbackFn, timeout) {
        var originalArgs = arguments;
        _ready.done(function () {
            _logger.debug.log(originalArgs, 'RECORD EVENT');
            callbackFn = utils.createSafeCallback(callbackFn, timeout);
            _kmqPushCommand('record', properties, callbackFn, name);
        }).fail(function () {
            if (_.isFunction(callbackFn)) {
                callbackFn();
            }
        });
    };

    /**
     * Tags an HTML element to record an event when its clicked
     * @param {string} selector - The ID or class of the element to track.
     * @param {string} name - The name of the event to record.
     * @param {object} properties - optional Properties related to the event being recorded.
     */
    var internalClick = function (selector, name, properties) {
        var originalArgs = arguments;
        _ready.done(function () {
            _logger.debug.log(_logger.fmt.labelArgs(["Selector", "Name", "Properties"], originalArgs), 'Setup Track Internal Click - only runs after click occurs');
            _kmq.push(['trackClick', selector, name, properties]);
        });
    };

    /**
     * Tags a link that takes someone to another domain and provides enough time to record an event when the link is clicked, before being redirected.
     * @param {string} selector - The ID or class of the element to track.
     * @param {string} name - The name of the event to record.
     * @param {object} properties - optional Properties related to the event being recorded.
     */
    var trackOutboundLink = function (selector, name, properties) {
        var originalArgs = arguments;
        _ready.done(function () {
            _logger.debug.log(_logger.fmt.labelArgs(["Selector", "Name", "Properties"], originalArgs), 'Setup Track Click on Outbound Link - only runs after click occurs');
            _kmq.push(['trackClickOnOutboundLink', selector, name, properties]);
        });
    };

    /**
     * Fetches value for a given AB Test.
     * @param testSlug
     * @returns {*|{}}
     */
    var getAbTest = function (testSlug) {
        return _allAbTests[testSlug];
    };

    /**
     * Run some code once all data and scripts are loaded.
     * @param callback
     * @returns Nothing
     */
    var whenReadyAlways = function (callback) {
        _ready.always(callback);
    };

    /**
    * Global events present on base.html
    */
    _ready.done(function () {
        trackOutboundLink("#cta-trial-days-remaining", "clicked on Days Remaining CTA in trial banner", {});
        internalClick('#cta-trial-tour-button', 'clicked Get Tour CTA in trial banner', {});
    });

    return {
        identify: identify,
        identifyTraits: identifyTraits,
        track: {
            event: trackEvent,
            internalClick: internalClick,
            outboundLink: trackOutboundLink,
        },
        getAbTest: getAbTest,
        whenReadyAlways: whenReadyAlways,
    };
});
