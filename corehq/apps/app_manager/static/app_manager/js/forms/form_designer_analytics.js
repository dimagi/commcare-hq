define("app_manager/js/forms/form_designer_analytics", [
    'analytix/js/google',
    'analytix/js/kissmetrix',
], function (
    google,
    kissmetrics,
) {
    function workflow(message) {
        kissmetrics.track.event(message);
    }

    function usage(label, group, message) {
        google.track.event(label, group, message);
    }

    function fbUsage(group, message) {
        usage("Form Builder", group, message);
    }

    return {
        fbUsage: fbUsage,
        usage: usage,
        workflow: workflow,
    };
});
