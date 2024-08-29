'use strict';

hqDefine("prototype/js/hq_htmx_select_all",[
    'underscore',
], function (_) {
    let htmx = window.htmx;
    document.body.addEventListener('htmx:configRequest', function (evt) {
        if (evt.detail.elt.hasAttribute('hq-hx-table-select-all')) {
            let isSelected = evt.detail.elt.checked,
                selectAllParam = "selectAllValues";

            if (evt.detail.elt.hasAttribute('hq-hx-table-select-all-param')) {
                selectAllParam = evt.detail.elt.getAttribute('hq-hx-table-select-all-param');
            }

            evt.detail.parameters[selectAllParam] = _.map(
                document.getElementsByClassName(evt.detail.elt.getAttribute('hq-hx-table-select-all')), function (el) {
                    el.checked = isSelected;

                    if (evt.detail.elt.hasAttribute('hq-hx-table-select-all-trigger')) {
                        htmx.trigger(el, evt.detail.elt.getAttribute('hq-hx-table-select-all-trigger'));
                    }

                    return el.value;
                });
        }
    });
});
