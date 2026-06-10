/*
*  Setters for the OCS chat widget's page context object.
*
*  One setter per supported field so the context shape stays fixed —
*  adding a new field is a deliberate change here.
*
*  Widget API: https://docs.openchatstudio.com/chat_widget/reference/#page-context
*/

const WIDGET_SELECTOR = 'open-chat-studio-widget';
let _currentContext = {};

function _publish() {
    const widget = document.querySelector(WIDGET_SELECTOR);
    if (widget) {
        widget.pageContext = _currentContext;
    }
}

function setUrl(url) {
    _currentContext.url = url;
    _publish();
}

function setPageTitle(page_title) {
    _currentContext.page_title = page_title;
    _publish();
}

function setDomain(domain) {
    _currentContext.domain = domain;
    _publish();
}

export default {
    setUrl: setUrl,
    setPageTitle: setPageTitle,
    setDomain: setDomain,
};
