import $ from "jquery";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import ocsContext, {WIDGET_SELECTOR} from "hqwebapp/js/ocs_widget_context_setter";

const FORMDESIGNER = '#formdesigner';
const PUBLISH_DEBOUNCE_MS = 1000;

function _vellum() {
    return $(FORMDESIGNER).vellum("get");
}

function extractFormXml(vellum) {
    return vellum.createXML({withCaseMappings: true});
}

function _publishXml() {
    const xml = extractFormXml(_vellum());
    if (xml) {
        ocsContext.setFormXml(xml);
    }
}

function extractQuestionTypes(form) {
    const types = {};
    form.walkMugs(function (mug) {
        if (mug.options.typeName) {
            types[mug.absolutePath] = mug.options.typeName;
        }
    });
    return types;
}

function _publishQuestionTypes() {
    const form = _vellum()?.data.core.form;
    if (!form) {
        return;
    }
    ocsContext.setQuestionTypes(extractQuestionTypes(form));
}

function buildSelectedQuestion(mug) {
    if (!mug) {
        return null;
    }
    const parent = mug.parentMug;
    const belongsToQuestion = parent && {
        type: parent.options.typeName,
        question_id: parent.p.nodeID,
        path: parent.hashtagPath,
    };

    if (mug.__className === "Choice") {
        return {
            type: mug.options.typeName,
            value: mug.p.nodeID,
            belongs_to_question: belongsToQuestion,
        };
    }
    if (mug.__className === "Itemset") {
        return {
            type: mug.options.typeName,
            belongs_to_question: belongsToQuestion,
        };
    }
    return {
        type: mug.options.typeName,
        question_id: mug.p.nodeID,
        path: mug.hashtagPath,
    };
}

function extractSelectedQuestion(vellum) {
    return buildSelectedQuestion(vellum?.getCurrentlySelectedMug());
}

function _publishCurrentSelectedQuestion() {
    ocsContext.setCurrentSelectedQuestion(extractSelectedQuestion(_vellum()));
}

function _initListener() {
    const vellum = _vellum();
    const form = vellum?.data.core.form;
    if (!form) {
        return;
    }
    _publishXml();
    _publishQuestionTypes();
    _publishCurrentSelectedQuestion();
    ocsContext.setModuleName(initialPageData.get('module_name'));
    form.on('change', _.debounce(function () {
        _publishXml();
        _publishQuestionTypes();
    }, PUBLISH_DEBOUNCE_MS));
    // User clicks a different question without editing doesn't fire form.change.
    vellum.data.core.$tree.on('select_node.jstree', _publishCurrentSelectedQuestion);
}

$(function () {
    if (!document.querySelector(WIDGET_SELECTOR)) {
        return;
    }
    document.addEventListener('vellum:ready', _initListener, {once: true});
});

export {extractFormXml, extractQuestionTypes, extractSelectedQuestion};
