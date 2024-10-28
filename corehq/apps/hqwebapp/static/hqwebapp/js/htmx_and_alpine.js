/**
 * Include this module as the entry point to use HTMX and Alpine.js on a page without
 * any additional configuration.
 *
 * NOTE: This entry point only supports Bootstrap 5 pages!
 * You can make your view support Bootstrap 5 by using the `@use_bootstrap5` decorator.
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
import 'commcarehq';
import 'hqwebapp/js/htmx_base';

import Alpine from 'alpinejs';
Alpine.start();
