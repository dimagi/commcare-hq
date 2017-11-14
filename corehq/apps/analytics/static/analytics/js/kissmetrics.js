/* globals _, _kmq */

var _kmq = _kmq || [];

hqDefine('analytics/js/kissmetrics', function () {
    'use strict';
    var _get = hqImport('analytics/js/initial').getFn('kissmetrics'),
        _abTests = hqImport('analytics/js/initial').getAbTests('kissmetrics'),
        logger = hqImport('analytics/js/logging').getLoggerForApi('Kissmetrics'),
        _utils = hqImport('analytics/js/utils'),
        _allAbTests = {},
        _init = {};

    logger.verbose.addCategory('data', 'DATA');
    logger.debug.addCategory('ab', 'AB TEST');

    window.dataLayer = window.dataLayer || [];

    var KmqWrapper = function (originalObject) {
        Array.call(this, originalObject);
    };
    KmqWrapper.prototype = Object.create(Array.prototype);
    KmqWrapper.prototype.constructor = KmqWrapper;
    KmqWrapper.prototype.push = function () {
        logger.deprecated.log(arguments, '_kmq.push');
        Array.prototype.push.apply(this, arguments);
    };
    KmqWrapper.prototype.pushNew = function () {
        Array.prototype.push.apply(this, arguments);
    };
    _kmq = new KmqWrapper(_kmq); // eslint-disable-line no-global-assign

    /**
     * Push data to _kmq by command type.
     * @param {string} commandName
     * @param {object} properties
     * @param {function|undefined} callbackFn - optional
     * @param {string|undefined} eventName - optional
     */
    var _kmqPushCommand = function (commandName, properties, callbackFn, eventName) {
        var command, data;
        command = _.compact([commandName, eventName, properties, callbackFn]);
        _kmq.pushNew(command);
        data = {
            event: 'km_' + commandName,
        };
        if (eventName) data.km_event = eventName;
        if (properties) data.km_property = properties;
        window.dataLayer.push(data);
        logger.verbose.log(command, ['window._kmq.push', 'window.dataLayer.push', '_kmqPushCommand', commandName]);
    };

    /**
     * Initialization function for kissmetrics libraries
     * @param srcUrl
     * @private
     */
    var _addKissmetricsScript = function (srcUrl) {
        logger.verbose.data(srcUrl, "Injected Script");
        _utils.insertAsyncScript(srcUrl);
    };

    _init.apiId = _get('apiId');
    logger.verbose.data(_init.apiId || "NONE SET", "API ID");

    // Initialize Kissmetrics
    if (_init.apiId) {
        _addKissmetricsScript('//i.kissmetrics.com/i.js');
        _addKissmetricsScript('//doug1izaerwt3.cloudfront.net/' + _init.apiId + '.1.js');
    }

    // Initialize Kissmetrics AB Tests
    _.each(_abTests, function (ab, testName) {
        var test = {};
        testName = _.last(testName.split('.'));
        if (_.isObject(ab) && ab.version) {
            test[ab.name || testName] = ab.version;
        } else if (!_.isEmpty(ab)) {
            test[testName] = ab;
        }
        if (!_.isEmpty(test)) {
            logger.debug.ab(test, "New Test: " + testName);
            _kmqPushCommand('set', test);
            _.extend(_allAbTests, test);
        }
    });

    /**
     * Identifies the current user
     * @param {string} identity - A unique ID to identify the session.
     */
    var identify = function (identity) {
        logger.debug.log(arguments, 'Identify');
        _kmqPushCommand('identify', identity);
    };

    /**
     * Sets traits for the current user
     * @param {object} traits - an object of traits
     * @param {function} callbackFn - (optional) callback function
     * @param {integer} timeout - (optional) timeout in milliseconds
     */
    var identifyTraits = function (traits, callbackFn, timeout) {
        logger.debug.log(logger.fmt.labelArgs(["Traits", "Callback Function", "Timeout"], arguments), 'Identify Traits (Set)');
        callbackFn = _utils.createSafeCallback(callbackFn, timeout);
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
        callbackFn = _utils.createSafeCallback(callbackFn, timeout);
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

    var getAbTest = function (testSlug) {
        return _allAbTests[testSlug] || {};
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
