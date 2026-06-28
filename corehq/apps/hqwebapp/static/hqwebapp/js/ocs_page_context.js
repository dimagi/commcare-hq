/*
*  Collects the OCS chat widget's page context on demand.
*
*  When the user sends a message the widget fires `ocs:message:before-send`.
*
*  Widget API: https://docs.openchatstudio.com/chat_widget/reference/#page-context
*/

const WIDGET_SELECTOR = 'open-chat-studio-widget';
const BEFORE_SEND_EVENT = 'ocs:message:before-send';

const _contextCollectors = [];

function registerContextCollector(collectContext) {
    _contextCollectors.push(collectContext);
}

function getClientPageContext() {
    return Object.assign(
        {},
        ..._contextCollectors.map((collectContext) => collectContext() || {}),
    );
}

document.addEventListener('DOMContentLoaded', function () {
    const widget = document.querySelector(WIDGET_SELECTOR);
    if (!widget) {
        return;
    }
    widget.addEventListener(BEFORE_SEND_EVENT, function () {
        widget.pageContext = getClientPageContext();
    });
});

export {WIDGET_SELECTOR};
export default {
    registerContextCollector: registerContextCollector,
};
