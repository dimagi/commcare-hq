/* globals _, _kmq */

// Deprecated analytics globals
var kmqPushSafe, // eslint-disable-line no-unused-vars
    analytics; // eslint-disable-line no-unused-vars

window.analytics = {};

// to support deprecated direct ga() calls
var ga = window.ga || function () {
    var _global = hqImport('analytics/js/initial').getFn('global');
    if (_global('isEnabled')) {
        hqImport('analytics/js/google').logger.warning.log(arguments, 'no global ga function was defined');
        if (arguments.length) {
            var lastArg = arguments[arguments.length - 1];
            if (lastArg) {
                var callback = lastArg.hitCallback;
                if (callback) {
                    callback();
                }
            }
        }
    }
};

/**
 * This creates wrappers with warnings around legacy global functions to help with refactoring of HQ's analytics.
 * Eventually this will be phased out and all the old globals replaced.
 */
hqDefine('analytics/js/deprecated', function () {
    'use strict';
    var _utils = hqImport('analytics/js/utils'),
        _kissmetrics = hqImport('analytics/js/kissmetrics'),
        _google = hqImport('analytics/js/google'),
        _global = hqImport('analytics/js/initial').getFn('global');

    /**
     * Helper function for wrapping the legacy functions.
     * @param {object} api - the analytics api
     * @param {string} fnName - Deprecated Function Name
     * @param {function} fallbackFn - Function to fallback to.
     * @param {function} formatArgs - (optional) Function that takes an array of arguments and reformats the arguments for fallback function.
     * @returns {Function} A function that takes the same paramers as the legacy function, but processes it in the new world and warns of its usage.
     * @private
     */
    var _makeLegacyFn = function(api, fnName, fallbackFn, formatArgs) {
        return function () {
            var args = Array.from(arguments);
            api.logger.deprecated.log(arguments, fnName);
            if (_.isFunction(formatArgs)) {
                args = formatArgs(args);
            }
            return fallbackFn.apply(null, args);
        };
    };

    /**
     * Gets the callback frunction (from Google Analytics' hitCallback) from the last argument, if available,
     * and re-adds to arguments
     * @param args - Array of arguments
     * @returns {array} - Array of arguments
     * @private
     */
    var _addCallbackToArgs = function (args) {
        var lastArg = _.last(args);
        if (lastArg && _.isFunction(lastArg.hitCallback)) {
            delete lastArg.hitCallback;
            args = _.union(args, [lastArg.hitCallback]);
        }
        return args;
    };
    if (_global('isEnabled')) {
        kmqPushSafe = _makeLegacyFn(_kissmetrics, 'kmqPushSafe', function (args, timeout) {
            var lastArg = _.last(args);
            args[args.length - 1] = _utils.createSafeCallback(lastArg, timeout);
            _kmq.push(args);
        });

        window.analytics.workflow = _makeLegacyFn(_kissmetrics, 'window.analytics.workflow', _kissmetrics.track.event);
        window.analytics.track = window.analytics.workflow;

        window.analytics.trackWorkflowLink = _makeLegacyFn(_kissmetrics, ' window.analytics.trackWorkflowLink', function(element, event, properties) {
            _utils.trackClickHelper(element, function (cb) {
                _kissmetrics.track.event(event, properties, cb);
            });
        });

        analytics = window.analytics;
    }
    return {};
});
