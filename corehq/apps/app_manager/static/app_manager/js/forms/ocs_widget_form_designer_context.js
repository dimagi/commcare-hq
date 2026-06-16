import $ from "jquery";
import _ from "underscore";
import ocsContext, {WIDGET_SELECTOR} from "hqwebapp/js/ocs_widget_context_setter";

const FORMDESIGNER = '#formdesigner';
const PUBLISH_DEBOUNCE_MS = 1000;

function _vellum() {
    return $(FORMDESIGNER).vellum("get");
}

function _publishXml() {
    const xml = $(FORMDESIGNER).vellum("createXML", {withCaseMappings: true});
    if (xml) {
        ocsContext.setFormXml(xml);
    }
}

function _publishQuestionTypes() {
    const form = _vellum()?.data?.core?.form;
    if (!form) {
        return;
    }
    const types = {};
    form.tree.walk(function (mug, _nodeID, processChildren) {
        if (mug && mug.options?.typeName) {
            types[mug.absolutePath] = mug.options.typeName;
        }
        processChildren();
    });
    ocsContext.setQuestionTypes(types);
}

function _initListener() {
    const form = _vellum()?.data?.core?.form;
    if (!form) {
        return;
    }
    _publishXml();
    _publishQuestionTypes();
    form.on('change', _.debounce(function () {
        _publishXml();
        _publishQuestionTypes();
    }, PUBLISH_DEBOUNCE_MS));
}

$(function () {
    if (!document.querySelector(WIDGET_SELECTOR)) {
        return;
    }
    document.addEventListener('vellum:ready', _initListener, {once: true});
});
