/**
 * Instantiates the Drift analytics and customer support messaging platform.
 */
hqDefine('analytix/js/drift', [
    'underscore',
    'analytix/js/initial',
    'analytix/js/logging',
    'analytix/js/utils',
    'analytix/js/hubspot',
], function (
    _,
    initialAnalytics,
    logging,
    utils,
    hubspot
) {
    'use strict';
    var _get = initialAnalytics.getFn('drift'),
        _drift = {},
        _logger = logging.getLoggerForApi('Drift'),
        _ready = $.Deferred(); // eslint-disable-line no-unused-vars

    $(function () {
        var apiId = _get('apiId'),
            scriptUrl = "https://js.driftt.com/include/" + utils.getDateHash() + "/" + apiId + '.js';

        _logger = logging.getLoggerForApi('Drift');
        _ready = utils.initApi(_ready, apiId, scriptUrl, _logger, function () {
            _drift = window.driftt = window.drift = window.driftt || [];
            if (!_drift.init && !_drift.invoked) {
                _drift.methods = [ "identify", "config", "track", "reset", "debug", "show", "ping", "page", "hide", "off", "on" ];
                _drift.factory = function (methodName) {
                    return function () {
                        var methodFn = Array.prototype.slice.call(arguments);
                        methodFn.unshift(methodName);
                        _drift.push(methodFn);
                        return _drift;
                    };
                };
                _.each(_drift.methods, function (methodName) {
                    _drift[methodName] = _drift.factory(methodName);
                });
            }

            _drift.SNIPPET_VERSION = '0.3.1';

            _drift.on('emailCapture',function (e) {
                hubspot.identify({email: e.data.email});
                hubspot.trackEvent('Identified via Drift');
            });

            $('#start-chat-cta-btn').click(function () {
                _drift.api.startInteraction({
                    interactionId: 51834,
                    goToConversation: true,
                });
            });

        });
    });

    // no methods just yet
    return 1;
});
