/*
    Make sure this module is included with HTMX projects so that the
    required CSRF Token is always added to the request headers.

    Alternatively you can include the `hx-headers` param in a parent element:
    ```
    hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'
    ```
 */
import htmx from 'htmx.org';

document.body.addEventListener('htmx:configRequest', (evt) => {
    // By default, HTMX does not allow cross-origin requests
    // We will double-check the config setting here out of an abundance of caution
    if (htmx.config.selfRequestsOnly) {
        evt.detail.headers['X-CSRFToken'] = document.getElementById('csrfTokenContainer').value;
    }
});
