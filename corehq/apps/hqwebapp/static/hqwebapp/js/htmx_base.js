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
// Update the default timeout to something reasonable
htmx.config.timeout = 20000;

import 'hqwebapp/js/htmx_utils/hq_hx_action';
import 'hqwebapp/js/htmx_utils/csrf_token';
import retryHtmxRequest from 'hqwebapp/js/htmx_utils/retry_request';
import { showHtmxErrorModal } from 'hqwebapp/js/htmx_utils/errors';

document.body.addEventListener('htmx:responseError', (evt) => {
    let errorCode = evt.detail.xhr.status;
    if (errorCode === 504) {
        if (!retryHtmxRequest(evt)) {
            showHtmxErrorModal(
                errorCode,
                gettext('Gateway Timeout Error: max retries exceeded')
            );
        }
        return;
    }
    showHtmxErrorModal(
        errorCode,
        evt.detail.xhr.statusText
    );
});

document.body.addEventListener('htmx:timeout', (evt) => {
    if (!retryHtmxRequest(evt)) {
        // show error modal
        showHtmxErrorModal(
            504,
            gettext('Gateway Timeout Error: max retries exceeded')
        );
    }
});
