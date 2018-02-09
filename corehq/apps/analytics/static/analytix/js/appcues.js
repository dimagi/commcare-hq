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
        _logger = logging.getLoggerForApi('AppCues'),
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

    return 1;
});
