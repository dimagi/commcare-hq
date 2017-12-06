/* global Array, window */

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
        _global = initialAnalytics.getFn('global'),
        _drift = {},
        _logger;

    $(function () {
        _logger = logging.getLoggerForApi('Drift');
        if (_global('isEnabled')) {
            _drift = window.driftt = window.drift = window.driftt || [];
            if (!_drift.init && !_drift.invoked ) {
                _drift.methods = [ "identify", "config", "track", "reset", "debug", "show", "ping", "page", "hide", "off", "on" ];
                _drift.factory = function (methodName) {
                    return function() {
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
            var apiId = _get('apiId');

            if (apiId) {
                var scriptUrl = "https://js.driftt.com/include/" + utils.getDateHash() + "/" + apiId + '.js';
                _logger.verbose.log(scriptUrl, "Adding Script");
                utils.insertScript(scriptUrl, _logger.debug.log, {
                    crossorigin: 'anonymous',
                });
            }
            _drift.on('emailCapture',function(e){
                hubspot.identify({email: e.data.email});
                hubspot.trackEvent('Identified via Drift');
            });

            _logger.debug.log("Initialized");
        }
    });

    // no methods just yet
    return 1;
});
