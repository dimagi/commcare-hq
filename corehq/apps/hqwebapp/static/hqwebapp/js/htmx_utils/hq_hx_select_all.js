/*
    The attribute `hq-hx-select-all` is used to select all checkboxes with the class name
    provided in the config object passed as a string in the attribute value.

    Example:
    hx-hx-select-all='{
        "selector": <string - class name of the checkboxes>,
        "triggerEvent": <string - name of the event to trigger on each checkbox>
    }'

*/
import htmx from 'htmx.org';

document.body.addEventListener('htmx:configRequest', (event) => {
    if (event.detail.elt.hasAttribute('hq-hx-select-all')) {
        const config = JSON.parse(event.detail.elt.getAttribute('hq-hx-select-all'));
        document.querySelectorAll(config.selector).forEach((el) => {
            el.checked = event.detail.elt.checked;
            if (config.triggerEvent) {
                htmx.trigger(el, config.triggerEvent);
            }
        });
    }
});
