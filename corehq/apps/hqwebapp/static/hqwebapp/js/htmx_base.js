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
import retryHtmxRequest from 'hqwebapp/js/htmx_utils/retry_request';
import { showHtmxErrorModal } from 'hqwebapp/js/htmx_utils/errors';

// By default, there is no timeout and requests hang indefinitely, so update to reasonable value.
htmx.config.timeout = 20000;  // 20 seconds, in milliseconds

const HTTP_BAD_GATEWAY = 504;
const HTTP_REQUEST_TIMEOUT = 408;

document.body.addEventListener('htmx:responseError', (evt) => {
    let errorCode = evt.detail.xhr.status;
    if (errorCode === HTTP_BAD_GATEWAY) {
        if (!retryHtmxRequest(evt.detail.elt, evt.detail.pathInfo, evt.detail.requestConfig)) {
            showHtmxErrorModal(
                errorCode,
                gettext('Gateway Timeout Error. Max retries exceeded.'),
            );
        }
        return;
    }
    showHtmxErrorModal(
        errorCode,
        evt.detail.xhr.statusText,
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
    if (!retryHtmxRequest(evt.detail.elt, evt.detail.pathInfo, evt.detail.requestConfig) && evt.detail.requestConfig.verb === 'get') {
        showHtmxErrorModal(
            HTTP_REQUEST_TIMEOUT,
            gettext('Request timed out. Max retries exceeded.'),
        );
    }
});
