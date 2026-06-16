import $ from "jquery";
import _ from "underscore";
import ocsContext, {WIDGET_SELECTOR} from "hqwebapp/js/ocs_widget_context_setter";

const FORMDESIGNER = '#formdesigner';
const PUBLISH_DEBOUNCE_MS = 1000;

function _publishXml() {
    const xml = $(FORMDESIGNER).vellum("createXML", {withCaseMappings: true});
    if (xml) {
        ocsContext.setFormXml(xml);
    }
}

function _initListener() {
    const form = $(FORMDESIGNER).vellum("get")?.data?.core?.form;
    if (!form) {
        return;
    }
    _publishXml();
    form.on('change', _.debounce(_publishXml, PUBLISH_DEBOUNCE_MS));
}

$(function () {
    if (!document.querySelector(WIDGET_SELECTOR)) {
        return;
    }
    document.addEventListener('vellum:ready', _initListener, {once: true});
});
