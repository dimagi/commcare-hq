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
    'analytix/js/utils',
], function (
    $,
    _,
    initialAnalytics,
    logging,
    utils
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

    $(function () {
        // userProperties are added to dataLayer at earliest to be readily available once GTM loads
        var apiId = _get('apiId');
        if (apiId && initialAnalytics.getFn('global')(('isEnabled'))) {
            addUserPropertiesToDataLayer();
        }

        var scriptUrl = '//www.googletagmanager.com/gtm.js?id=' + apiId;
        _ready = utils.initApi(_ready, apiId, scriptUrl, _logger, function () {
            gtmSendEvent('gtm.js', {'gtm.start': new Date().getTime()});
        });
    });

    return {
        sendEvent: gtmSendEvent,
    };
});
