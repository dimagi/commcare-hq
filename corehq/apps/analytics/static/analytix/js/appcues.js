/* global Appcues */

/**
 * Instantiates the AppCues analytics and customer support messaging platform.
 */
hqDefine('analytix/js/appcues', [
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
    var _get = initialAnalytics.getFn('appcues'),
        _ready = $.Deferred(),
        _logger = logging.getLoggerForApi('Appcues'),
        EVENT_TYPES = {
            FORM_LOADED: "Form is loaded",
            FORM_SAVE: "Saved a form",
            FORM_SUBMIT: "Submitted a form",
            POPPED_OUT_PREVIEW: "Popped out preview",
            QUESTION_CREATE: "Added a question to a form",
        };

    $(function () {
        window.AppcuesSettings = {
            skipAMD: true,
            enableURLDetection: true,
        };
        var apiId = _get('apiId'),
            scriptUrl = "//fast.appcues.com/" + apiId + '.js';

        const allUserProperties = getIdentityProperties(
            initialAnalytics.getNamespacedProperties('appcues'));
        const username = allUserProperties['username'];
        const userProperties = _.omit(allUserProperties, 'username');

        _logger = logging.getLoggerForApi('Appcues');
        _ready = utils.initApi(_ready, apiId, scriptUrl, _logger, function () {
            identify(username, userProperties);
        });
    });

    function identify(email, properties) {
        var originalArgs = arguments;
        _ready.done(function () {
            _logger.debug.log(originalArgs, 'Identify');
            Appcues.identify(email, properties);
        });
    }

    const PROD_INSTANCE = 'www';

    function getIdentityProperties(rawProperties) {
        const publicProperties = _.omit(rawProperties, 'apiId');

        const nameMap = {
            'dateCreated': 'createdAt',
            'userIsDimagi': 'isDimagi',
        };

        const result = {};
        _.each(publicProperties, function (value, key) {
            const mappedKey = _.get(nameMap, key, key);
            result[mappedKey] = value;
        });

        result['email'] = result['username'];

        if ('instance' in result && result['instance'] !== PROD_INSTANCE) {
            result['instance'] = result['instance'] || 'UNKNOWN';
            // ensure non-prod environments do not conflict with prod environments
            result['username'] = result['username'] + '@' + result['instance'];
        }

        return result;
    }

    function trackEvent(label, data) {
        var originalArgs = arguments;
        _ready.done(function () {
            _logger.debug.log(originalArgs, 'RECORD EVENT');
            if (_.isObject(data)) {
                Appcues.track(label, data);
            } else {
                Appcues.track(label);
            }
        });
    }

    function then(successCallback, failureCallback) {
        _ready.then(successCallback, failureCallback);
    }

    return {
        identify: identify,
        trackEvent: trackEvent,
        EVENT_TYPES: EVENT_TYPES,
        then: then,
    };
});
