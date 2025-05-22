/**
 *  To use:
 *
 *     1) In your page's entry point, import HTMX and this module, eg:
 *
 *     import 'htmx.org';
 *     import 'hqwebapp/js/htmx_utils/hq_hx_action';
 *
 *     2) Then, make sure your class-based view extends the `HqHtmxActionMixin`.
 *
 *     3) Apply the `@hq_hx_action()` decorator to methods you want to make available to
 *        `hq-hx-action` attributes
 *
 *     4) Reference that method in the `hq-hx-action` attribute alongside `hx-get`,
 *        `hx-post`, or equivalent
 */
document.body.addEventListener('htmx:configRequest', (evt) => {
    // Require that the hq-hx-action attribute is present
    if (evt.detail.elt.hasAttribute('hq-hx-action')) {
        const action = evt.detail.elt.getAttribute('hq-hx-action');
        // insert HQ-HX-Action in the header to be processed by the `HqHtmxActionMixin`
        evt.detail.headers['HQ-HX-Action'] = action;

        /*
            Below we namespace the URL with a flag in the querystring so that
            the browser keys the cache for each partial separately.

            It also creates distinct log paths for each hq-hx-action--helpful for troubleshooting.

            This querystring flag will be removed by `HqHtmxActionMiddleware` so that it
            doesn't accidentally get passed around to other requests.
        */
        const url = new URL(evt.detail.path, window.location.origin);
        url.searchParams.set('_hq-hx-action', action);
        evt.detail.path = url.pathname + url.search;
    }
});
