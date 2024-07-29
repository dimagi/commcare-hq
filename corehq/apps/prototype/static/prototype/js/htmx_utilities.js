'use strict';

hqDefine("prototype/js/htmx_utilities",[
    'es6!hqwebapp/js/bootstrap5_loader',
], function (
    bootstrap
) {
    let self = {},
        htmx = window.htmx,
        htmxRetryPathCounts = {};

    self.MAX_RETRIES = 20;

    self.triggerErrorModal = function (errorModalId, errorCode, errorText) {
        let modal = new bootstrap.Modal(document.getElementById(errorModalId));
        window.dispatchEvent(new CustomEvent('updateHtmxRequestErrorModal', {
            detail: {
                errorCode: errorCode,
                errorText: errorText,
            },
        }));
        modal.show();
    };

    self.retryHtmxRequest = function (evt, errorModalId) {
        // where evt is an HTMX event
        let updateUrl = evt.detail.elt.getAttribute('hx-replace-url'),
            requestPath = evt.detail.pathInfo.finalRequestPath;

        if (htmxRetryPathCounts[requestPath] === undefined) {
            htmxRetryPathCounts[requestPath] = 0;
        }
        htmxRetryPathCounts[requestPath] ++;

        if (htmxRetryPathCounts[requestPath] > self.MAX_RETRIES) {
            self.triggerErrorModal(
                errorModalId,
                504,
                'Gateway Timeout Error: ' + self.MAX_RETRIES + " retries exceeded"
            );
            return;
        }

        let context = {
            source: evt.detail.elt,
            target: evt.detail.requestConfig.target,
            swap: evt.detail.elt.getAttribute('hx-swap'),
            headers: evt.detail.requestConfig.headers,
            values: JSON.parse(evt.detail.elt.getAttribute('hx-vals')),
        };

        htmx.ajax(
            evt.detail.requestConfig.verb,
            requestPath,
            context
        ).then(function () {
            if (updateUrl) {
                updateUrl = window.location.origin + window.location.pathname + updateUrl;
                window.history.pushState(null, '', updateUrl);
            }
            delete htmxRetryPathCounts[requestPath];
        });

    };

    return self;
});
