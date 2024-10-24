import htmx from 'htmx.org';

const DEFAULT_MAX_RETRIES = 20;
const retryPathCounts = {};

/**
 * Retries an HTMX request up to a specified max retry count.
 *
 * @param {Object} elt - The HTMX element object (usually found in evt.detail.elt)
 * @param {Object} pathInfo - The HTMX pathInfo object (usually found in evt.detail.pathInfo)
 * @param {Object} requestConfig - The HTMX requestConfig object (usually found in evt.detail.requestConfig)
 * @param {number} [maxRetries=DEFAULT_MAX_RETRIES] - The maximum number of retries allowed.
 * @returns {boolean} - Returns `false` if max retries are exceeded, otherwise `true`.
 */
const retryHtmxRequest = (elt, pathInfo, requestConfig, maxRetries = DEFAULT_MAX_RETRIES) => {
    // Extract values from the HTMX event
    const replaceUrl = elt.getAttribute('hx-replace-url');
    const requestPath = pathInfo.finalRequestPath;

    // Initialize retry count if necessary
    retryPathCounts[requestPath] = retryPathCounts[requestPath] || 0;
    retryPathCounts[requestPath]++;

    // Return false if the max number of retries for that path has been exceeded
    if (retryPathCounts[requestPath] > maxRetries) {
        return false;
    }

    // Prepare the context for the htmx request
    const context = {
        source: elt,
        target: requestConfig.target,
        swap: elt.getAttribute('hx-swap'),
        headers: requestConfig.headers,
        values: JSON.parse(elt.getAttribute('hx-vals')),
    };

    // Make the htmx request and handle URL update if necessary
    htmx.ajax(requestConfig.verb, requestPath, context).then(() => {
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
