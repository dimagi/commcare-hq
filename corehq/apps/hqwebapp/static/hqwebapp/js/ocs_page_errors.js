/*
 *  Collects the error and warning messages currently shown to the user, for the
 *  OCS chat widget's page context, by scraping the rendered error UI from the DOM.
 *
 *  Judging relevance (a real error the user faces vs. a decorative/informational banner)
 *  is deliberately left to the chat widget.
 */

import ocsContext from "hqwebapp/js/ocs_page_context";

const SCRAPE_SELECTORS = [
    {selector: '.alert-danger', level: 'error', type: 'banner'},
    {selector: '.alert-warning', level: 'warning', type: 'banner'},
];

function _elementText(element) {
    const clone = element.cloneNode(true);
    clone.querySelectorAll(
        '.btn-close, .close, [data-dismiss], [data-bs-dismiss], .sr-only, .visually-hidden',
    ).forEach((node) => node.remove());
    return (clone.textContent || "").replace(/\s+/g, " ").trim();
}

function _isReportable(element) {
    // offsetParent is null when the element or an ancestor is display:none.
    // Vellum has its own collector in ocs_widget_form_designer_context.js
    return element.offsetParent !== null && !element.closest('#formdesigner');
}

function _scrapeErrorMessages() {
    const messages = [];
    SCRAPE_SELECTORS.forEach(({selector, level, type}) => {
        document.querySelectorAll(selector).forEach((element) => {
            if (!_isReportable(element)) {
                return;
            }
            const message = _elementText(element);
            messages.push({level, message, type});
        });
    });
    return messages;
}

function _collectPageWarnings() {
    const messages = _scrapeErrorMessages();
    return messages.length ? {page_warnings: messages} : {};
}

ocsContext.registerContextCollector(_collectPageWarnings);

export const exportedForTesting = {
    _collectPageWarnings,
    _scrapeErrorMessages,
};
