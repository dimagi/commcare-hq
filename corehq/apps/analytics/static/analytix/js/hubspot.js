
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
    ctaForms,
) {
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
        if (_get('isDemoVisible')) {
            _utils.loadDemoForm();
        }

    });

    /**
     * Activates the Hubspot Request Demo form
     */
    _utils.loadDemoForm = function () {
        let isTrial = _get('isDemoTrial'),
            isVariant = _get('demoABv2') && _get('demoABv2').version === 'variant',
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
            showPreferredLanguage: false,
            nextButtonText: gettext("Submit Request"),
            submitCallbackFn: function () {
                $('#get-demo-cta-success').fadeIn();
                $('#get-demo-cta-form-content').addClass('hidden').addClass('d-none'); // todo after bootstrap 5 migration

                kissmetrics.track.event("Demo Workflow - Contact Info Received");
            },
        });
        if ($form.length) {
            $form.koApplyBindings(demoForm);
        }

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
