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
        _logger = logging.getLoggerForApi('Appcues'),
        _ready = $.Deferred();

    $(function () {
        var apiId = _get('apiId'),
            scriptUrl = "//fast.appcues.com/" + apiId + '.js';

        _ready = utils.initApi(_ready, apiId, scriptUrl, _logger, function () {
            Appcues.identify(_get("userId"), {
                firstName: _get("firstName"),
                lastName: _get("lastName"),
                email: _get("email"),
                createdAt: _get("createdAt"),
                isDimagi: _get("isDimagi"),
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
    return {
        trackEvent: trackEvent,
    };
});
