"use strict";
/**
 *  Handles communication with the google tag manager API.
 *  gtx is the filename because some ad blockers blocks 'gtm.js'*
 */
hqDefine('analytix/js/gtx', [
    'jquery',
    'underscore',
    'analytix/js/initial',
    'analytix/js/logging',
], function (
    $,
    _,
    initialAnalytics,
    logging
) {
    var _get = initialAnalytics.getFn('gtm'),
        _logger = logging.getLoggerForApi('Google Tag Manager'),
        _ready = $.Deferred();


    window.dataLayer = window.dataLayer || [];

    function addUserPropertiesToDataLayer() {
        var userPropertiesEvent = {
            event: 'userProperties',
            userId: _get('userId', 'none'),
            isDimagi: _get('userIsDimagi', 'no', 'yes'),
            isCommCare: _get('userIsCommCareUser', 'no', 'yes'),
            domain: _get('domain', 'none'),
            hqEnvironment: _get('hqInstance', 'none'),
            isTestDomain: _get('isTestDomain', 'none'),
            isDomainActive: _get('isDomainActive', 'no', 'yes'),
            domainSubscription: _get('domainSubscription', 'none'),
            domainSubscriptionEdition: _get('domainSubscriptionEdition', 'none'),
            domainSubscriptionServiceType: _get('domainSubscriptionServiceType', 'none'),
        };
        window.dataLayer.push(userPropertiesEvent);
    }

    /**
     * Helper function to send event to Google Tag Manager.
     * @param {string} eventName
     * @param {object} eventData
     * @param {function|undefined} callbackFn - optional
     */
    var gtmSendEvent = function (eventName, eventData, callbackFn) {
        _ready.done(function () {
            var data = {
                event: eventName,
            };
            if (eventData) {
                _.extend(data, eventData);
            }
            window.dataLayer.push(data);
            _logger.verbose.log(eventName, 'window.dataLayer.push');
        }).fail(function () {
            if (_.isFunction(callbackFn)) {
                callbackFn();
            }
        });
    };

    /**
     * Modified version of utils.initApi to enable GTM on the India environment.
     * This does not checks for `global.isEnabled` and instead directly checks for the environment See 'gtm.html'.
     * This is done to avoid enabling other analytics tooling on the India environment.
     * See the PR description (https://github.com/dimagi/commcare-hq/pull/35238) for more details.
    */
    var initApi = function (ready, apiId, isGTMEnabled, scriptUrls, logger, initCallback) {
        logger.verbose.log(apiId || "NOT SET", ["DATA", "API ID"]);

        if (_.isString(scriptUrls)) {
            scriptUrls = [scriptUrls];
        }
        
        // This check 'isGTMEnabled' is different from the original function and its value is set in 'gtm.html'
        if (!isGTMEnabled) {
            logger.debug.log("Failed to initialize because analytics are disabled");
            ready.reject();
            return ready;
        }

        if (!apiId) {
            logger.debug.log("Failed to initialize because apiId was not provided");
            ready.reject();
            return ready;
        }

        $.when.apply($, _.map(scriptUrls, function (url) { return $.getScript(url); }))
            .done(function () {
                if (_.isFunction(initCallback)) {
                    initCallback();
                }
                logger.debug.log('Initialized');
                ready.resolve();
            }).fail(function () {
                logger.debug.log("Failed to Load Script - Check Adblocker");
                ready.reject();
            });

        return ready;
    };


    $(function () {
        // userProperties are added to dataLayer at earliest to be readily available once GTM loads
        var apiId = _get('apiId');
        var isGTMEnabled = _get('isGTMEnabled');

        if (apiId && isGTMEnabled) {
            addUserPropertiesToDataLayer();
        }

        var scriptUrl = '//www.googletagmanager.com/gtm.js?id=' + apiId;
        _ready = initApi(_ready, apiId, isGTMEnabled, scriptUrl, _logger, function () {
            gtmSendEvent('gtm.js', {'gtm.start': new Date().getTime()});
        });
    });

    return {
        sendEvent: gtmSendEvent,
    };
});
