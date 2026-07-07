/*
*  Collects the OCS chat widget's page context on demand.
*
*  When the user sends a message the widget fires `ocs:message:before-send`.
*
*  Widget API: https://docs.openchatstudio.com/chat_widget/reference/#page-context
*/

import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";

const WIDGET_SELECTOR = 'open-chat-studio-widget';
const BEFORE_SEND_EVENT = 'ocs:message:before-send';

const _contextCollectors = [];

function registerContextCollector(collectContext) {
    _contextCollectors.push(collectContext);
}

function _domainFromUrl() {
    const match = window.location.pathname.match(/^\/a\/([^/]+)\//);
    return match ? match[1] : null;
}

// Fetch once on load; role rarely changes and the endpoint is cached server-side.
let _roleContext = {};

function _fetchMyRole() {
    let url;
    try {
        url = initialPageData.reverse('my_role');
    } catch {
        // my_role URL only exists on domain pages
        return;
    }
    $.getJSON(url).done(function (data) {
        _roleContext = data;
    });
}

function collectGlobalContext() {
    return Object.assign({
        url: window.location.href,
        page_title: document.title,
        domain: _domainFromUrl(),
    }, _roleContext);
}

function runCollector(collectContext) {
    try {
        return collectContext() || {};
    } catch (error) {
        console.error("OCS context collector failed");
        return {};
    }
}

function getClientPageContext() {
    const context = collectGlobalContext();
    for (const collectContext of _contextCollectors) {
        Object.assign(context, runCollector(collectContext));
    }
    return context;
}

document.addEventListener('DOMContentLoaded', function () {
    const widget = document.querySelector(WIDGET_SELECTOR);
    if (!widget) {
        return;
    }
    _fetchMyRole();
    widget.addEventListener(BEFORE_SEND_EVENT, function () {
        widget.pageContext = getClientPageContext();
    });
});

export {WIDGET_SELECTOR};
export default {
    registerContextCollector: registerContextCollector,
};
