import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import ocsContext from "hqwebapp/js/ocs_widget_context_setter";

var WIDGET_SELECTOR = 'open-chat-studio-widget';

function _domainFromUrl() {
    var match = window.location.pathname.match(/^\/a\/([^/]+)\//);
    return match ? match[1] : null;
}

function _fetchMyRole() {
    var url;
    try {
        url = initialPageData.reverse('my_role');
    } catch {
        // URL only registered on domain-scoped pages — nothing to fetch elsewhere.
        return;
    }
    $.getJSON(url)
        .done(function (data) {
            if (data.role !== undefined) {
                ocsContext.setRole(data.role);
            }
            if (data.is_dimagi_admin !== undefined) {
                ocsContext.setIsDimagiAdmin(data.is_dimagi_admin);
            }
            if (data.is_domain_admin !== undefined) {
                ocsContext.setIsDomainAdmin(data.is_domain_admin);
            }
            if (data.is_enterprise_admin !== undefined) {
                ocsContext.setIsEnterpriseAdmin(data.is_enterprise_admin);
            }
            if (data.permissions !== undefined) {
                ocsContext.setPermissions(data.permissions);
            }
        })
}

function _setInitialContext() {
    ocsContext.setUrl(window.location.href);
    ocsContext.setPageTitle(document.title);
    ocsContext.setDomain(_domainFromUrl());
}

function _observePageTitleChanges() {
    var titleEl = document.querySelector('title');
    if (!titleEl) {
        return;
    }
    var observer = new MutationObserver(function () {
        ocsContext.setPageTitle(document.title);
    });
    observer.observe(titleEl, {
        childList: true,
        characterData: true,
        subtree: true,
    });
}

function _observeUrlChanges() {
    window.addEventListener('hashchange', ocsContext.setUrl(window.location.href));
    window.addEventListener('popstate', ocsContext.setUrl(window.location.href));
}

// Only listen to top window to ignore App Preview iframe
if (window === window.top) {
    document.addEventListener('DOMContentLoaded', function () {
        if (!document.querySelector(WIDGET_SELECTOR)) {
            return;
        }
        _setInitialContext();
        _observePageTitleChanges();
        _observeUrlChanges();
        _fetchMyRole();
    });
}
