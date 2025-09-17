/**
 * DO NOT include this module as a `js_entry` point!
 * Use `hqwebapp/js/htmx_and_alpine` for entry points.
 *
 * This module requires Alpine to properly display the HTMX error modal.
 *
 * Instead, use this module as a starting point when you require additional javascript configuration for Alpine
 * before `Alpine.start()` is called. For instance, you want to access `Alpine.data()` or other globals.
 *
 * e.g.:
 *
 *      import 'hqwebapp/js/htmx_base';
 *      import Alpine from 'alpinejs';
 *
 *      // access Alpine globals
 *      Alpine.data(....);
 *
 *      Alpine.start();
 *
 * Tips:
 * - Use the `HqHtmxActionMixin` to group related HTMX calls and responses as part of one class based view.
 * - To show errors encountered by HTMX requests, include the `hqwebapp/htmx/error_modal.html` template
 *   in the `modals` block of the page, or `include` a template that extends it.
 */
import htmx from 'htmx.org';

import 'hqwebapp/js/htmx_utils/hq_hx_action';
import 'hqwebapp/js/htmx_utils/csrf_token';
import 'hqwebapp/js/htmx_utils/hq_hx_loading';
import 'hqwebapp/js/htmx_utils/hq_hx_refresh';
import retryUtils from 'hqwebapp/js/htmx_utils/retry_request';
import { showHtmxErrorModal } from 'hqwebapp/js/htmx_utils/errors';

// By default, there is no timeout and requests hang indefinitely, so update to reasonable value.
htmx.config.timeout = 20000;  // 20 seconds, in milliseconds

const HTTP_BAD_GATEWAY = 504;
const HTTP_REQUEST_TIMEOUT = 408;

document.body.addEventListener('htmx:responseError', (evt) => {
    let errorCode = evt.detail.xhr.status;
    let errorText = evt.detail.xhr.statusText;
    let showDetails = true;

    const xhr = evt.detail.xhr;
    const hqHxActionError = xhr.getResponseHeader('HQ-HX-Action-Error');
    if (hqHxActionError) {
        let errorData = {};
        try {
            errorData = JSON.parse(hqHxActionError);
        } catch (e) {
            console.error('Failed to parse HQ-HX-Action-Error header:', e);
        }
        errorCode = errorData.status_code || errorCode;
        errorText = errorData.message || errorText;
        showDetails = errorData.show_details;
        const maxRetries = errorData.max_retries || retryUtils.DEFAULT_MAX_RETRIES;
        if (errorData.retry_after && retryUtils.isRetryAllowed(evt, maxRetries)) {
            setTimeout(() => {
                retryUtils.retryHtmxRequest(evt.detail.elt, evt.detail.pathInfo, evt.detail.requestConfig);
            }, errorData.retry_after);
            return;
        }
    }
    if (errorCode === HTTP_BAD_GATEWAY) {
        if (retryUtils.isRetryAllowed(evt)) {
            retryUtils.retryHtmxRequest(evt.detail.elt, evt.detail.pathInfo, evt.detail.requestConfig);
            return;
        }
        errorText = gettext('Gateway Timeout Error. Max retries exceeded.');
    }
    showHtmxErrorModal(
        errorCode,
        errorText,
        evt,
        showDetails,
    );
});

document.body.addEventListener('htmx:timeout', (evt) => {
    /**
     * Safely retry on GET request timeouts. Use caution on other types of requests.
     *
     * If you want retry on POST requests, please create a new `js_entry` point and add a
     * similar event listener there. Also, you may want to adjust the `htmx.config.timeout`
     * value as well.
     */
    if (retryUtils.isRetryAllowed(evt) && evt.detail.requestConfig.verb === 'get') {
        retryUtils.retryHtmxRequest(evt.detail.elt, evt.detail.pathInfo, evt.detail.requestConfig);
    } else {
        showHtmxErrorModal(
            HTTP_REQUEST_TIMEOUT,
            gettext('Request timed out. Max retries exceeded.'),
            evt,
        );
    }
});
