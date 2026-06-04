import ocs_context from "hqwebapp/js/ocs_widget_context_setter";

function _domainFromUrl() {
    var match = window.location.pathname.match(/^\/a\/([^/]+)\//);
    return match ? match[1] : null;
}

function _setInitialContext() {
    ocs_context.setUrl(window.location.href);
    ocs_context.setPageTitle(document.title);
    ocs_context.setDomain(_domainFromUrl());
}

function _observePageTitleChanges() {
    var titleEl = document.querySelector('title');
    if (!titleEl) {
        return;
    }
    var observer = new MutationObserver(function () {
        ocs_context.setPageTitle(document.title);
    });
    observer.observe(titleEl, {
        childList: true,
        characterData: true,
        subtree: true,
    });
}

function _observeUrlChanges() {
    window.addEventListener('hashchange', ocs_context.setUrl(window.location.href));
    window.addEventListener('popstate', ocs_context.setUrl(window.location.href));
}

// Only listen to top window to ignore App Preview iframe
if (window === window.top) {
    document.addEventListener('DOMContentLoaded', function () {
        _setInitialContext();
        _observePageTitleChanges();
        _observeUrlChanges();
    });
}
