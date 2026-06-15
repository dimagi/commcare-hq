import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import ocsContext, {WIDGET_SELECTOR} from "hqwebapp/js/ocs_widget_context_setter";

function _text(el) {
    return el?.textContent.trim() ?? '';
}

function _readStructure() {
    return {
        app_name: _text(document.querySelector('[data-ocs-app-name]')),
        current_language: initialPageData.get('lang'),
        available_languages: initialPageData.get('langs_for_ocs_context') || [],
        modules: [].slice.call(document.querySelectorAll('[data-ocs-module]')).map(function (moduleEl) {
            return {
                name: _text(moduleEl.querySelector('[data-ocs-module-name]')),
                forms: [].slice.call(moduleEl.querySelectorAll('[data-ocs-form-name]')).map(_text),
            };
        }),
    };
}

function _readDomThenUpdate() {
    if (!document.querySelector('[data-ocs-app-name]')) {
        return;
    }
    ocsContext.setAppStructure(_readStructure());
}

$(function () {
    if (!document.querySelector(WIDGET_SELECTOR)) {
        return;
    }
    _readDomThenUpdate();

    $(document).on('inline-edit-save', _readDomThenUpdate);
});
