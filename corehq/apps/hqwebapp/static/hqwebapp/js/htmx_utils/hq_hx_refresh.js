/*
    Used to chain an `hqRefresh` event to a related HTMX element making a request.

    The attribute `hq-hx-refresh-after` sends the `hqRefresh` event to the target selector
    element on `htmx:afterRequest`.

    THe attribute `hq-hx-refresh-swap` sends the `hqRefresh` event to the target selector
    element on `htmx:afterSwap`.

    The value of the attributes should be a css selector--for example, `#element` where element is the CSS id.

    The target element can then apply `hx-trigger="hqRefresh"`, effectively chaining a refresh event to the
    original triggering request.

    This is commonly used to trigger a refresh of tabular data with Django Tables using the `BaseHtmxTable`
    subclass. However, it can be used to chain other HTMX elements together
 */
import htmx from 'htmx.org';

const handleRefresh = (evt, attribute) => {
    if (evt.detail.elt.hasAttribute(attribute)) {
        htmx.trigger(evt.detail.elt.getAttribute(attribute), 'hqRefresh');
    }
};

document.body.addEventListener('htmx:afterRequest', (evt) => {
    handleRefresh(evt, 'hq-hx-refresh-after');
});

document.body.addEventListener('htmx:afterSwap', (evt) => {
    handleRefresh(evt, 'hq-hx-refresh-swap');
});
