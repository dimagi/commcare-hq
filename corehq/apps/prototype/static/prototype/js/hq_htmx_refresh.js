'use strict';

hqDefine("prototype/js/hq_htmx_refresh",[
], function () {
    let htmx = window.htmx;
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        if (evt.detail.elt.hasAttribute('hq-hx-refresh')) {
            htmx.trigger(evt.detail.elt.getAttribute('hq-hx-refresh'), 'hqRefresh');
        }
    });
});
