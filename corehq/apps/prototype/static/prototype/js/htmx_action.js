document.body.addEventListener('htmx:configRequest', function (evt) {
    if (evt.detail.elt.hasAttribute('hx-action')) {
        // Add hx action header to request if hx-action attribute is present
        evt.detail.headers['HX-Action'] = evt.detail.elt.getAttribute('hx-action');
    }
});
