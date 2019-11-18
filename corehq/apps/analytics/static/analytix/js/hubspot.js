/* globals window, hbspt */
/**
 * Instatiates the Hubspot analytics platform.
 */
hqDefine('analytix/js/hubspot', [
    'underscore',
    'analytix/js/initial',
    'analytix/js/logging',
    'analytix/js/utils',
    'analytix/js/kissmetrix',
], function (
    _,
    initialAnalytics,
    logging,
    utils,
    kissmetrics
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
                        var isTrial = _get('isDemoTrial'),
                            isVariant = _get('demoABv2').version === 'variant',
                            formId;

                        if (isTrial) {
                            formId = isVariant ? "c2381f55-9bd9-4f27-8476-82900e58bfd6" : "4474515e-fea6-4154-b3cf-1fe42b1c1333";
                        } else {
                            formId = isVariant ? "f6ebf161-fccf-4083-9a72-5839a0c8ac8c" : "d1897875-a5bb-4b63-9b9c-3d8fdbbe8274";
                        }

                        _utils.loadDemoForm(apiId, formId);
                    });
            });
        }

    });

    /**
     * Loads the Hubspot Request Demo form and loads a Schedule Once Calendar
     * Widget for auto-booking an appointment as soon as the form is submitted.
     * @param {string} apiId
     * @param {string} formId
     */
    _utils.loadDemoForm = function (apiId, formId) {
        hbspt.forms.create({
            portalId: apiId,
            formId: formId,
            target: "#get-demo-cta-form-content",
            css: "",
            onFormReady: function () {
                var $hubspotFormModal = $('#cta-form-get-demo'),
                    hasInteractedWithForm = false;

                $hubspotFormModal.on('shown.bs.modal', function () {
                    kissmetrics.track.event("Demo Workflow - Viewed Form");
                });

                $hubspotFormModal.on('hide.bs.modal', function () {
                    kissmetrics.track.event("Demo Workflow - Dismissed Form");
                });

                $('#get-demo-cta-form-content').find('input').click(function () {
                    if (!hasInteractedWithForm) {
                        kissmetrics.track.event("Demo Workflow - Interacted With Form");
                        hasInteractedWithForm = true;
                    }
                });
            },
            onFormSubmit: function ($form) {
                $('#get-demo-cta-calendar-content').fadeIn();
                $('#get-demo-cta-form-content').addClass('hide');

                var email = $form.find('[name="email"]').val(),
                    firstname = $form.find('[name="firstname"]').val(),
                    lastname = $form.find('[name="lastname"]').val(),
                    newUrl = document.location.href + '?email=' + email + '&name=' + firstname + '%20' + lastname;

                kissmetrics.track.event("Demo Workflow - Contact Info Received");

                // This nastiness is required for Schedule Once to auto-fill
                // required fields. Sending snark the way of the S.O. devs...
                window.history.pushState({}, document.title, newUrl);

                // Causes the Schedule Once form to populate the element
                // #SOIDIV_commcaredemoform as soon as it loads. Once it's
                // loaded this does not leave the page.
                $.getScript('//cdn.scheduleonce.com/mergedjs/so.js')
                    .done(function () {
                        kissmetrics.track.event("Demo Workflow - Loaded Booking Options");
                        setTimeout(function () {
                            // This is a bit of a hack, but the only way to detect if
                            // the Schedule Once Form was submitted on our side.
                            // The style attribute changes when the form is successfully
                            // submitted.
                            var lastKnownHeight = 0,
                                observer = new MutationObserver(function (mutations) {
                                    mutations.forEach(function () {
                                        var newHeight = $('#SOI_commcaredemoform').height();
                                        if (newHeight < lastKnownHeight) {
                                            var coreUrl = document.location.href.split('?')[0];
                                            kissmetrics.track.event("Demo Workflow - Demo Scheduled");
                                            $('#cta-form-get-demo').off('hide.bs.modal');
                                            window.history.pushState({}, document.title, coreUrl);
                                        }
                                        lastKnownHeight = newHeight;

                                    });
                            });
                            // target is the the iframe containing the schedule once form
                            var target = document.getElementById('SOI_commcaredemoform');
                            observer.observe(target, { attributes: true, attributeFilter: ['style'] });
                        }, 3000);
                    });
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
