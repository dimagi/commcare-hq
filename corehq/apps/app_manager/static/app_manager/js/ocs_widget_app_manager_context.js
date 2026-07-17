import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import {SELECTORS} from "app_manager/js/preview_app_constants";
import ocsContext, {WIDGET_SELECTOR} from "hqwebapp/js/ocs_page_context";

function _text(el) {
    return el?.textContent.trim() ?? '';
}

function _readStructure() {
    return {
        app_name: _text(document.querySelector('[data-ocs-app-name]')),
        current_language: initialPageData.get('lang'),
        available_languages: initialPageData.get('langs_for_ocs_context') || [],
        modules: [...document.querySelectorAll('[data-ocs-module]')].map(function (moduleEl) {
            return {
                name: _text(moduleEl.querySelector('[data-ocs-module-name]')),
                forms: [...moduleEl.querySelectorAll('[data-ocs-form-name]')].map(_text),
            };
        }),
    };
}

function _collectAppStructureContext() {
    if (!document.querySelector('[data-ocs-app-name]')) {
        return {};
    }
    return {app_structure: _readStructure()};
}

function _collectAppPreviewContext() {
    const errors = (
        document.querySelector(SELECTORS.PREVIEW_WINDOW_IFRAME)?.contentWindow
        .getAppPreviewErrors?.()
    ) || [];
    return errors.length ? {app_preview_warnings: errors} : {};
}

$(function () {
    if (!document.querySelector(WIDGET_SELECTOR)) {
        return;
    }
    ocsContext.registerContextCollector(_collectAppStructureContext);
    ocsContext.registerContextCollector(_collectAppPreviewContext);
});
