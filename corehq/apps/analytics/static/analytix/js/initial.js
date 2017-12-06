/**
 *  Fetches all the initialization data needed for the different analytics platforms.
 */
hqDefine('analytix/js/initial', [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    initialPageData
) {
    'use strict';
    var _selector = '.initial-analytics-data',
        _gather =  initialPageData.gather,
        _initData = {},
        _abSelector = '.analytics-ab-tests',
        _abTests,
        _abTestsByApi = {};

    /**
     * Helper function to create the namespaced slug for the initial_analytics_data
     * eg apiName.key
     * @param {string} apiName
     * @param {string} key
     * @returns {string}
     * @private
     */
    var _getSlug = function (apiName, key) {
        return apiName + '.' + key;
    };

    /**
     * Get the namespaced initial_analytics_data value.
     * @param {string} apiName
     * @param {string} key
     * @returns {*} value
     * @private
     */
    var _getNamespacedData = function (apiName, key) {
        /*if (document.readyState !== "complete") {
            throw new Error("Attempt to call _getNamespacedData before document is ready");
        }*/

        var slug = _getSlug(apiName, key);
        if (_initData[slug] === undefined) {
            _initData = _gather(_selector, _initData);
        }
        return _initData[slug];
    };

    /**
     * Returns a get function namespaced to the specified API.
     * @param apiName
     * @returns {Function}
     */
    var getFn = function (apiName) {
        /**
         * Helper function for returning the data
         * @param {string} key
         * @param {*} optDefault - (optional) value returned if the fetched value is undefined or false
         * @param {*} optTrue - (optional) value returned if the fetched value is true
         */
        return function (key, optDefault, optTrue) {
            var data = _getNamespacedData(apiName, key);
            if (optTrue !== undefined) {
                data = data ? optTrue : optDefault;
            } else {
                data = data || optDefault;
            }
            return data;
        };
    };

    /**
     * Fetches all AB Tests for a given API name
     * @param {string} apiName
     * @returns {array} array of abTests
     */
    var getAbTests = function (apiName) {
        if (_.isUndefined(_abTests)) {
            _abTests = _gather(_abSelector, {});
        }
        if (_.isUndefined(_abTestsByApi[apiName])) {
            _abTestsByApi[apiName] = _.compact(_.map(_abTests, function (val, key) {
                if (key.startsWith(apiName)) {
                    return {
                        slug: _.last(key.split('.')),
                        context: val,
                    };
                }
            }));
        }
        return _abTests;
    };

    $(function() {
        _initData = _gather(_selector, _initData);
    });

    return {
        getFn: getFn,
        getAbTests: getAbTests,
    };
});
