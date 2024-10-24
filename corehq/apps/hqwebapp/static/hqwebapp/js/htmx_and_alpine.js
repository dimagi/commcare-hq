/**
 * Include this module as the entry point to use HTMX and Alpine.js on a page without
 * any additional configuration.
 *
 * e.g.:
 *
 *      {% js_entry "hqwebapp/js/htmx_and_alpine" %}
 *
 * Tips:
 * - Use the `HqHtmxActionMixin` to group related HTMX calls and responses as part of one class based view.
 * - To show errors encountered by HTMX requests, include the `hqwebapp/htmx/error_modal.html` template
 *   in the `modals` block of the page, or `include` a template that extends it.
 */
import 'hqwebapp/js/htmx_base';

import Alpine from 'alpinejs';
Alpine.start();
