/*
    Adds an `is-loading` class to the element with ID specified in the `hq-hx-loading` attribute.
    This `is-loading` class is applied when to that ID before an HTMX request begins, and is
    removed after an HTMX swap is completed.

    This is useful for adding loading indicators to elements outside the parent heirarchy available
    through using `hx-indicator` alone. Right now, this is used to add an `is-loading` style to a django tables
    table, which overlays a loading indicator across the entire table (seen in hqwebapp/tables/bootstrap5_htmx.html)
 */
document.body.addEventListener('htmx:beforeRequest', (evt) => {
    if (evt.detail.elt.hasAttribute('hq-hx-loading')) {
        let loadingElt = document.getElementById(evt.detail.elt.getAttribute('hq-hx-loading'));
        if (loadingElt) {
            loadingElt.classList.add('is-loading');
        }
    }
});
document.body.addEventListener('htmx:afterSwap', (evt) => {
    if (evt.detail.elt.hasAttribute('hq-hx-loading')) {
        let loadingElt = document.getElementById(evt.detail.elt.getAttribute('hq-hx-loading'));
        if (loadingElt && loadingElt.classList.contains('is-loading')) {
            loadingElt.classList.remove('is-loading');
        }
    }
});
