/* globals window, hbspt */
/**
 * Instatiates the Hubspot analytics platform.
 */
hqDefine('analytix/js/hubspot', [
    'jquery',
    'underscore',
    'analytix/js/initial',
    'analytix/js/logging',
    'analytix/js/utils',
    'analytix/js/kissmetrix',
    'analytix/js/cta_forms',
], function (
    $,
    _,
    initialAnalytics,
    logging,
    utils,
    kissmetrics,
    ctaForms
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

        // these forms get processed on the backend, so they don't need the hubspot js to be loaded
        _utils.loadTrialForm();
        if (_get('isDemoVisible')) {
            _utils.loadDemoForm();
        }

    });

    /**
     * Activates the Hubspot Request Demo form and loads a Schedule Once Calendar
     * Widget for auto-booking an appointment as soon as the form is submitted.
     */
    _utils.loadDemoForm = function () {
        let isTrial = _get('isDemoTrial'),
            isVariant = _get('demoABv2').version === 'variant',
            $modal = $('#cta-form-get-demo'),
            $form = $('#get-demo-cta-form-content'),
            hasInteractedWithForm = false,
            formId,
            demoForm;

        if (isTrial) {
            formId = isVariant ? "c2381f55-9bd9-4f27-8476-82900e58bfd6" : "4474515e-fea6-4154-b3cf-1fe42b1c1333";
        } else {
            formId = isVariant ? "f6ebf161-fccf-4083-9a72-5839a0c8ac8c" : "d1897875-a5bb-4b63-9b9c-3d8fdbbe8274";
        }

        demoForm = ctaForms.hubspotCtaForm({
            hubspotFormId: formId,
            showContactMethod: isVariant,
            showPreferredLanguage: false,
            useWhatsApp: false,
            useGoogleHangouts: true,
            nextButtonText: gettext("Book a Time"),
            phoneNumberSelector: $form.find('input[name="phone"]'),
            submitCallbackFn: function () {
                $('#get-demo-cta-calendar-content').fadeIn();
                $('#get-demo-cta-form-content').addClass('hidden');

                kissmetrics.track.event("Demo Workflow - Contact Info Received");

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
                            let lastKnownHeight = 0,
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
                            let target = document.getElementById('SOI_commcaredemoform');
                            observer.observe(target, { attributes: true, attributeFilter: ['style'] });
                        }, 3000);
                    });
            },
        });
        $form.koApplyBindings(demoForm);

        $modal.on('shown.bs.modal', function () {
            kissmetrics.track.event("Demo Workflow - Viewed Form");
        });
        $modal.on('hide.bs.modal', function () {
            kissmetrics.track.event("Demo Workflow - Dismissed Form");
        });

        $form.find('input').click(function () {
            if (!hasInteractedWithForm) {
                kissmetrics.track.event("Demo Workflow - Interacted With Form");
                hasInteractedWithForm = true;
            }
        });
    };

    /**
     * Activates the Hubspot Request Trial form and loads a Schedule Once Calendar
     * Widget for auto-booking an appointment as soon as the form is submitted.
     */
    _utils.loadTrialForm = function () {
        let $modal = $('#cta-form-start-trial'),
            $form = $('#get-trial-cta-form-content'),
            hasInteractedWithForm = false,
            trialForm;

        trialForm = ctaForms.hubspotCtaForm({
            hubspotFormId: '9c8ecc33-b088-474e-8f4c-1b10fae50c2f',
            showContactMethod: true,
            showPreferredLanguage: true,
            useWhatsApp: true,
            useGoogleHangouts: false,
            nextButtonText: gettext("Next"),
            phoneNumberSelector: $form.find('input[name="phone"]'),
            submitCallbackFn: function () {
                kissmetrics.track.event("Get Trial Workflow - Contact Info Received");
                // This nastiness is required for Schedule Once to auto-fill
                // required fields. Sending snark++ the way of the S.O. devs...

                // on form submitted?
                $('#choose-callback-options').toggleClass('hidden');
                $('#get-trial-cta-form-content').addClass('hidden');
                $('#start-trial-modal-header').text(gettext("Your trial request has been received!"));
            },
        });
        $form.koApplyBindings(trialForm);

        $modal.on('shown.bs.modal', function () {
            kissmetrics.track.event("Get Trial Workflow - Viewed Form");
        });
        $modal.on('hide.bs.modal', function () {
            kissmetrics.track.event("Get Trial Workflow - Dismissed Form");
        });

        $form.find('input').click(function () {
            if (!hasInteractedWithForm) {
                kissmetrics.track.event("Get Trial Workflow - Interacted With Form");
                hasInteractedWithForm = true;
            }
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
