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

function setRole(role) {
    _currentContext.role = role;
    _publish();
}

function setIsDimagiAdmin(isDimagiAdmin) {
    _currentContext.is_dimagi_admin = isDimagiAdmin;
    _publish();
}

function setIsDomainAdmin(isDomainAdmin) {
    _currentContext.is_domain_admin = isDomainAdmin;
    _publish();
}

function setIsEnterpriseAdmin(isEnterpriseAdmin) {
    _currentContext.is_enterprise_admin = isEnterpriseAdmin;
    _publish();
}

function setPermissions(permissions) {
    _currentContext.permissions = permissions;
    _publish();
}

export default {
    setUrl: setUrl,
    setPageTitle: setPageTitle,
    setDomain: setDomain,
    setRole: setRole,
    setIsDimagiAdmin: setIsDimagiAdmin,
    setIsDomainAdmin: setIsDomainAdmin,
    setIsEnterpriseAdmin: setIsEnterpriseAdmin,
    setPermissions: setPermissions,
};
