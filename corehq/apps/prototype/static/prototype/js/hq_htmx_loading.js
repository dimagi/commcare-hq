'use strict';

hqDefine("prototype/js/hq_htmx_loading",[
], function () {
    let htmx = window.htmx;
    document.body.addEventListener('htmx:beforeRequest', function (evt) {
        if (evt.detail.elt.hasAttribute('hq-hx-loading')) {
            let loadingElt = document.getElementById(evt.detail.elt.getAttribute('hq-hx-loading'));
            if (loadingElt) {
                loadingElt.classList.add('is-loading');
            }
        }
    });
    document.body.addEventListener('htmx:afterRequest', function (evt) {
        if (evt.detail.elt.hasAttribute('hq-hx-loading')) {
            let loadingElt = document.getElementById(evt.detail.elt.getAttribute('hq-hx-loading'));
            if (loadingElt && loadingElt.classList.contains('is-loading')) {
                loadingElt.classList.remove('is-loading');
            }
        }
    });
});
