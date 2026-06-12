import ocsContext from "hqwebapp/js/ocs_widget_context_setter";

function _domainFromUrl() {
    var match = window.location.pathname.match(/^\/a\/([^/]+)\//);
    return match ? match[1] : null;
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
        _setInitialContext();
        _observePageTitleChanges();
        _observeUrlChanges();
    });
}
