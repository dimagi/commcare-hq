/* globals _, _kmq */

// Deprecated analytics globals
var analytics; // eslint-disable-line no-unused-vars

window.analytics = {};

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

    return {};
});
