/*
    Sends an `hqRefresh` event to the selector (element) specified in the `hq-hx-refresh` attribute.
 */
import htmx from 'htmx.org';

document.body.addEventListener('htmx:afterSwap', (evt) => {
    if (evt.detail.elt.hasAttribute('hq-hx-refresh')) {
        htmx.trigger(evt.detail.elt.getAttribute('hq-hx-refresh'), 'hqRefresh');
    }
});
