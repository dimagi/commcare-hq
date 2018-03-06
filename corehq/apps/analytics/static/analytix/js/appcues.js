/* global Appcues, Array, window */

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
        EVENT_TYPES = {
            FORM_SAVE: "Saved a form",
            FORM_SUBMIT: "Submitted a form",
            POPPED_OUT_PREVIEW: "Popped out preview",
            QUESTION_CREATE: "Added a question to a form",
        };

    $(function () {
        var apiId = _get('apiId'),
            scriptUrl = "//fast.appcues.com/" + apiId + '.js',
            _logger = logging.getLoggerForApi('Appcues');

        _ready = utils.initApi(_ready, apiId, scriptUrl, _logger, function () {
            Appcues.identify(_get("username"), {
                firstName: _get("firstName"),
                lastName: _get("lastName"),
                email: _get("username"),
                createdAt: _get("dateCreated"),
                isDimagi: _get("userIsDimagi"),
                instance: _get("instance"),
            });
        });
    });

    function trackEvent(label, data) {
        _ready.done(function () {
            if (_.isObject(data)) {
                Appcues.track(label, data);
            } else {
                Appcues.track(label);
            }
        });
    }
    function then(callback) {
        _ready.then(callback, callback);
    }

    return {
        trackEvent: trackEvent,
        EVENT_TYPES: EVENT_TYPES,
        then: then,
    };
});
