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
        _global = initialAnalytics.getFn('global'),
        logger = logging.getLoggerForApi('Kissmetrics'),
        _allAbTests = {},
        _init = {};

    window.dataLayer = window.dataLayer || [];

    /**
     * Push data to _kmq by command type.
     * @param {string} commandName
     * @param {object} properties
     * @param {function|undefined} callbackFn - optional
     * @param {string|undefined} eventName - optional
     */
    var _kmqPushCommand = function (commandName, properties, callbackFn, eventName) {
        if (_global('isEnabled')) {
            var command, data;
            command = _.compact([commandName, eventName, properties, callbackFn]);
            _kmq.push(command);
            data = {
                event: 'km_' + commandName,
            };
            if (eventName) data.km_event = eventName;
            if (properties) data.km_property = properties;
            window.dataLayer.push(data);
            logger.verbose.log(command, ['window._kmq.push', 'window.dataLayer.push', '_kmqPushCommand', commandName]);
        } else if (callbackFn) {
            callbackFn();
        }
    };

    /**
     * Initialization function for kissmetrics libraries
     * @param srcUrl
     * @private
     */
    var _addKissmetricsScript = function (srcUrl) {
        utils.insertScript(srcUrl, logger.debug.log);
    };

    var __init__ = function () {
        _init.apiId = _get('apiId');
        logger.verbose.log(_init.apiId || "NONE SET", "API ID");

        // Initialize Kissmetrics
        if (_init.apiId) {
            _addKissmetricsScript('//i.kissmetrics.com/i.js');
            _addKissmetricsScript('//doug1izaerwt3.cloudfront.net/' + _init.apiId + '.1.js');
        }

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
                logger.debug.log(test, ["AB Test", "New Test: " + testName]);
                _kmqPushCommand('set', test);
                _.extend(_allAbTests, test);
            }
        });
    };

    $(function() {
        if (_global('isEnabled')) {
            __init__();
            logger.debug.log("Initialized");
        }
    });

    /**
     * Identifies the current user
     * @param {string} identity - A unique ID to identify the session. Typically the user's email address.
     */
    var identify = function (identity) {
        if (_global('isEnabled')) {
            logger.debug.log(arguments, 'Identify');
            _kmqPushCommand('identify', identity);
        }
    };

    /**
     * Sets traits for the current user
     * @param {object} traits - an object of traits
     * @param {function} callbackFn - (optional) callback function
     * @param {integer} timeout - (optional) timeout in milliseconds
     */
    var identifyTraits = function (traits, callbackFn, timeout) {
        logger.debug.log(logger.fmt.labelArgs(["Traits", "Callback Function", "Timeout"], arguments), 'Identify Traits (Set)');
        callbackFn = utils.createSafeCallback(callbackFn, timeout);
        _kmqPushCommand('set', traits, callbackFn);
    };

    /**
     * Records an event and its properties
     * @param {string} name - Name of event to be tracked
     * @param {object} properties - (optional) Properties related to the event being tracked
     * @param {function} callbackFn - (optional) Function to be called after the event is tracked.
     * @param {integer} timeout - (optional) Timeout for safe callback
     */
    var trackEvent = function (name, properties, callbackFn, timeout) {
        logger.debug.log(arguments, 'RECORD EVENT');
        callbackFn = utils.createSafeCallback(callbackFn, timeout);
        _kmqPushCommand('record', properties, callbackFn, name);
    };

    /**
     * Tags an HTML element to record an event when its clicked
     * @param {string} selector - The ID or class of the element to track.
     * @param {string} name - The name of the event to record.
     * @param {object} properties - optional Properties related to the event being recorded.
     */
    var internalClick = function (selector, name, properties) {
        logger.debug.log(logger.fmt.labelArgs(["Selector", "Name", "Properties"], arguments), 'Track Internal Click');
        _kmqPushCommand('trackClick', properties, undefined, name);
    };

    /**
     * Tags a link that takes someone to another domain and provides enough time to record an event when the link is clicked, before being redirected.
     * @param {string} selector - The ID or class of the element to track.
     * @param {string} name - The name of the event to record.
     * @param {object} properties - optional Properties related to the event being recorded.
     */
    var trackOutboundLink = function (selector, name, properties) {
        logger.debug.log(logger.fmt.labelArgs(["Selector", "Name", "Properties"], arguments), 'Track Click on Outbound Link');
        _kmqPushCommand('trackClickOnOutboundLink', properties, undefined, name);
    };

    /**
     * Fetches value for a given AB Test.
     * @param testSlug
     * @returns {*|{}}
     */
    var getAbTest = function (testSlug) {
        return _allAbTests[testSlug];
    };

    return {
        logger: logger,
        identify: identify,
        identifyTraits: identifyTraits,
        track: {
            event: trackEvent,
            internalClick: internalClick,
            outboundLink: trackOutboundLink,
        },
        getAbTest: getAbTest,
    };
});
