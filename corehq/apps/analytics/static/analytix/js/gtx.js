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

    function setAllowedTagTypes() {
        // https://developers.google.com/tag-platform/tag-manager/restrict
        // Only allow tags, triggers, and variables we actively use.
        // Others may come with unknown security risks.
        var allowList = [
            'google',   // class that includes GA4 tags, built-in triggers and variables, etc.
        ];

        // Explicitly block tags, triggers, and variables with known security risks.
        // Note: blocklist overrides allowlist
        var blockList = [
            // Higher risk: running arbitrary code in the browser, DOM manipulation
            'jsm',      // custom javascript variable
            'html',     // custom html tag

            // Lower risk: data leakage
            'img',      // custom image tag
            'j',        // javascript variable
            'k',        // first party cookie variable
        ];
        window.dataLayer.push({'gtm.allowlist': allowList, 'gtm.blocklist': blockList});
    }

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
        var apiId = _get('apiId');
        var projectGAOptOut = _get('projectGAOptOut');

        // Tag Manager is solely used for Google Analytics. If a projects opts out of GA, we disable it here.
        // In case we decide to use Tag Manager for other tooling in future, remove this check and instead
        // add it for all the GA events at the Tag Manager Console end.
        if (projectGAOptOut === 'yes') {
            _logger.debug.log("Tag manager not initialized because Project has opted out of GA.");
            return;
        }

        // userProperties are added to dataLayer at earliest to be readily available once GTM loads
        if (apiId && initialAnalytics.getFn('global')(('isEnabled'))) {
            setAllowedTagTypes();
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
