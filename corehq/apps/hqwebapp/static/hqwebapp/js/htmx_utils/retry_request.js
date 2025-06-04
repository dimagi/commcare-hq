import htmx from 'htmx.org';

const DEFAULT_MAX_RETRIES = 20;
const RETRY_HEADER = 'HQ-HX-Retry';

/**
 * Retries an HTMX request and increments the retry count in the request headers.
 *
 * @param {Object} elt - The HTMX element object (usually found in evt.detail.elt)
 * @param {Object} pathInfo - The HTMX pathInfo object (usually found in evt.detail.pathInfo)
 * @param {Object} requestConfig - The HTMX requestConfig object (usually found in evt.detail.requestConfig)
 */
const retryHtmxRequest = (elt, pathInfo, requestConfig) => {
    const replaceUrl = elt.getAttribute('hx-replace-url');
    const requestPath = pathInfo.finalRequestPath;

    let retryCount = 0;
    if (RETRY_HEADER in requestConfig.headers) {
        retryCount = parseInt(requestConfig.headers[RETRY_HEADER], 10);
    }
    requestConfig.headers[RETRY_HEADER] = retryCount + 1;

    // Prepare the context for the htmx request
    const context = {
        source: elt,
        target: requestConfig.target,
        swap: elt.getAttribute('hx-swap'),
        headers: requestConfig.headers,
        values: JSON.parse(elt.getAttribute('hx-vals')),
    };

    // Make the htmx request and handle URL update if necessary
    htmx.ajax(requestConfig.verb, requestPath, context)
        .then(() => {
            if (replaceUrl === 'true') {
                window.history.pushState(null, '', requestPath);
            } else if (replaceUrl) {
                const newUrl = `${window.location.origin}${window.location.pathname}${replaceUrl}`;
                window.history.pushState(null, '', newUrl);
            }
        })
        .catch((error) => {
            console.error(`Error during HTMX request to ${requestPath}:`, error);
        });
};

const isRetryAllowed = (evt, maxRetries = DEFAULT_MAX_RETRIES) => {
    let retryCount = 0;
    if (evt.detail.requestConfig.headers && RETRY_HEADER in evt.detail.requestConfig.headers) {
        retryCount = parseInt(evt.detail.requestConfig.headers[RETRY_HEADER], 10);
    }
    return retryCount < maxRetries;
};

export default {
    retryHtmxRequest: retryHtmxRequest,
    isRetryAllowed: isRetryAllowed,
    DEFAULT_MAX_RETRIES: DEFAULT_MAX_RETRIES,
};
