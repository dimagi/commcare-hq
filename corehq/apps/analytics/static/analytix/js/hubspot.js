/* globals window, hbspt */
/**
 * Instatiates the Hubspot analytics platform.
 */
hqDefine('analytix/js/hubspot', [
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
    var _get = initialAnalytics.getFn('hubspot'),
        _logger = logging.getLoggerForApi('Hubspot'),
        _ready = $.Deferred(),
        _utils = {};

    var _hsq = window._hsq = window._hsq || [];

    $(function () {
        var apiId = _get('apiId'),
            scriptUrl = '//js.hs-analytics.net/analytics/' + utils.getDateHash() + '/' + apiId + '.js';

        _logger = logging.getLoggerForApi('Hubspot');
        _ready = utils.initApi(_ready, apiId, scriptUrl, _logger);


        // load demo request forms
        if (_get('isDemoVisible')) {
            _ready.done(function () {
                var formScriptUrls = ['//js.hsforms.net/forms/v2.js'];
                if ($('html').hasClass('lt-ie9')) {
                    formScriptUrls = _.union(['//js.hsforms.net/forms/v2-legacy.js'], formScriptUrls);
                }

                $.when.apply($, _.map(formScriptUrls, function (url) { return $.getScript(url); }))
                    .done(function () {
                        _utils.loadOldDemoForm(apiId);
                        _utils.loadDemoForm(apiId);
                    });
            });
        }

    });

    /**
    * Loads the Legacy Hubspot Demo Form (to be phased out after A/B test
    * @param {string} apiId
    */
    _utils.loadOldDemoForm = function (apiId) {
        hbspt.forms.create({
            portalId: apiId,
            formId: "0f5de42e-b562-4ece-85e5-cfd2db97eba8",
            target: "#get-demo-cta-form-body",
            css: "",
        });
    };

    /**
     * Loads the Hubspot Request Demo form and loads a Schedule Once Calendar
     * Widget for auto-booking an appointment as soon as the form is submitted.
     * @param {string} apiId
     */
    _utils.loadDemoForm = function (apiId) {
        hbspt.forms.create({
            portalId: apiId,
            formId: "38980202-f1bd-412e-b490-f390f40e9ee1",
            target: "#get-demo-cta-form-content",
            css: "",
            onFormSubmit: function ($form) {
                $('#get-demo-cta-calendar-content').fadeIn();
                $('#get-demo-cta-form-content').addClass('hide');

                var email = $form.find('[name="email"]').val(),
                    firstname = $form.find('[name="firstname"]').val(),
                    lastname = $form.find('[name="lastname"]').val(),
                    newUrl = document.location.href + '?email=' + email + '&name=' + firstname + '%20' + lastname;

                // This nastiness is required for Schedule Once to auto-fill
                // required fields. Sending snark the way of the S.O. devs...
                window.history.pushState(
                    "dimagi-contact-url " + document.title, document.title, newUrl
                );

                // Causes the Schedule Once form to populate the element
                // #SOIDIV_commcaredemoform as soon as it loads. Once it's
                // loaded this does not leave the page.
                $.getScript('//cdn.scheduleonce.com/mergedjs/so.js');

            },
        });
    };

    /**
     * Sends data to Hubspot to identify the current session.
     * @param {object} data
     */
    var identify = function (data) {
        _ready.done(function () {
            _logger.debug.log(data, "Identify");
            _hsq.push(['identify', data]);
        });
    };

    /**
     * Tracks an event through the Hubspot API
     * @param {string} eventId - The ID of the event. If you created the event in HubSpot, use the numerical ID of the event.
     * @param {integer|float} value - This is an optional argument that can be used to track the revenue of an event.
     */
    var trackEvent = function (eventId, value) {
        var originalArgs = arguments;
        _ready.done(function () {
            _logger.debug.log(_logger.fmt.labelArgs(["Event ID", "Value"], originalArgs), 'Track Event');
            _hsq.push(['trackEvent', {
                id: eventId,
                value: value,
            }]);
        });
    };

    var then = function (successCallback, failureCallback) {
        _ready.then(successCallback, failureCallback);
    };

    return {
        identify: identify,
        then: then,
        trackEvent: trackEvent,
    };
});
