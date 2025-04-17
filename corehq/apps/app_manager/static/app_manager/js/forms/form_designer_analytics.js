define("app_manager/js/forms/form_designer_analytics", [
    'analytix/js/google',
    'analytix/js/kissmetrix',
], function (
    google,
    kissmetrics,
) {
    function workflow(message) {
console.log("workflow: " + message);
        kissmetrics.track.event(message);
    }

    function usage(label, group, message) {
console.log("usage: " + group);
        google.track.event(label, group, message);
    }

    function fbUsage(group, message) {
console.log("fbUsage: " + group);
        usage("Form Builder", group, message);
    }

    return {
        fbUsage: fbUsage,
        usage: usage,
        workflow: workflow,
    };
});
