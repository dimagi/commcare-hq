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
    {selector: '.invalid-feedback', level: 'error', type: 'inline'},
    {selector: '.error-message', level: 'error', type: 'inline'},
    {selector: '.has-error .help-block', level: 'error', type: 'inline'},
    // The shared HTMX error modal.
    {selector: '#htmxRequestErrorModal .modal-body', level: 'error', type: 'modal'},
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

// Label for an inline field error.
// Walk up to a field wrapper, then take its first label/legend.
// Wrappers:
//   [id^="div_"]  — crispy forms (#div_id_<field>)
//   .form-group   — Bootstrap 3 field groups
//   fieldset      — grouped inputs with a <legend>
//   .q            — Web Apps questions
function _fieldLabel(element) {
    const container = element.closest('[id^="div_"], .form-group, fieldset, .q');
    const label = container && container.querySelector('label, legend');
    return label ? _elementText(label) : '';
}

function _documentsToScrape() {
    const roots = [document];
    const previewDoc = document.querySelector('iframe.preview-phone-window')?.contentDocument;
    if (previewDoc) {
        roots.push(previewDoc);
    }
    return roots;
}

function _scrapeErrorMessages() {
    const messages = [];
    _documentsToScrape().forEach((root) => {
        SCRAPE_SELECTORS.forEach(({selector, level, type}) => {
            root.querySelectorAll(selector).forEach((element) => {
                if (!_isReportable(element)) {
                    return;
                }
                let message = _elementText(element);
                if (type === 'inline') {
                    const label = _fieldLabel(element);
                    message = label ? `${label}: ${message}` : message;
                }
                messages.push({level, message, type});
            });
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
