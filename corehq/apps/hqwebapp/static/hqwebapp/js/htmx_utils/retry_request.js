import htmx from 'htmx.org';

const DEFAULT_MAX_RETRIES = 20;
let retryPathCounts = {};

/**
 * Retries an HTMX request up to a specified max retry count.
 *
 * @param {Object} evt - The HTMX event object containing details about the request.
 * @param {number} [maxRetries=DEFAULT_MAX_RETRIES] - The maximum number of retries allowed.
 * @returns {boolean} - Returns `false` if max retries are exceeded, otherwise `true`.
 */
const retryHtmxRequest = (evt, maxRetries = DEFAULT_MAX_RETRIES) => {
    // Extract values from the HTMX event
    const replaceUrl = evt.detail.elt.getAttribute('hx-replace-url');
    const requestPath = evt.detail.pathInfo.finalRequestPath;

    // Initialize retry count if necessary
    retryPathCounts[requestPath] = retryPathCounts[requestPath] || 0;
    retryPathCounts[requestPath]++;

    // Return false if the max number of retries for that path has been exceeded
    if (retryPathCounts[requestPath] > maxRetries) {
        return false;
    }

    // Prepare the context for the htmx request
    const context = {
        source: evt.detail.elt,
        target: evt.detail.requestConfig.target,
        swap: evt.detail.elt.getAttribute('hx-swap'),
        headers: evt.detail.requestConfig.headers,
        values: JSON.parse(evt.detail.elt.getAttribute('hx-vals')),
    };

    // Make the htmx request and handle URL update if necessary
    htmx.ajax(evt.detail.requestConfig.verb, requestPath, context).then(() => {
        if (replaceUrl === 'true') {
            window.history.pushState(null, '', requestPath);
        } else if (replaceUrl) {
            const newUrl = `${window.location.origin}${window.location.pathname}${replaceUrl}`;
            window.history.pushState(null, '', newUrl);
        }
        delete retryPathCounts[requestPath];
    });

    return true;
};

export default retryHtmxRequest;
