define('analytix/js/noopMetrics', [], function () {
    /**
     * Records an event and its properties
     * @param {string} name - Name of event to be tracked
     * @param {object} properties - (optional) Properties related to the event being tracked
     * @param {function} callbackFn - (optional) Function to be called after the event is tracked.
     * @param {integer} timeout - (optional) Timeout for safe callback
     */
    var trackEvent = function () {
        // leave as noop
    };

    /**
     * Tags an HTML element to record an event when its clicked
     * @param {string} selector - The ID or class of the element to track.
     * @param {string} name - The name of the event to record.
     * @param {object} properties - optional Properties related to the event being recorded.
     */
    var internalClick = function () {
        // leave as noop
    };

    /**
     * Tags a link that takes someone to another domain and provides enough time to record an event when the link is clicked, before being redirected.
     * @param {string} selector - The ID or class of the element to track.
     * @param {string} name - The name of the event to record.
     * @param {object} properties - optional Properties related to the event being recorded.
     */
    var trackOutboundLink = function () {
        // leave as noop
    };

    return {
        track: {
            event: trackEvent,
            internalClick: internalClick,
            outboundLink: trackOutboundLink,
        },
    };
});
