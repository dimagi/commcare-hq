import $ from "jquery";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
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
    form.walkMugs(function (mug) {
        if (mug.options?.typeName) {
            types[mug.absolutePath] = mug.options.typeName;
        }
    });
    ocsContext.setQuestionTypes(types);
}

function _buildSelectedQuestion(mug) {
    if (!mug) {
        return null;
    }
    const parent = mug.parentMug;
    const belongsToQuestion = parent && {
        type: parent.options.typeName,
        question_id: parent.p.nodeID || undefined,
        path: parent.hashtagPath || undefined,
    };

    if (mug.__className === "Choice") {
        return {
            type: mug.options.typeName,
            value: mug.p.nodeID || undefined,
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
        question_id: mug.p.nodeID || undefined,
        path: mug.hashtagPath || undefined,
    };
}

function _publishCurrentSelectedQuestion() {
    ocsContext.setCurrentSelectedQuestion(
        _buildSelectedQuestion(_vellum()?.getCurrentlySelectedMug()),
    );
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
    // User clicks a different question without editing don't fire form.change.
    vellum.data.core.$tree.on('select_node.jstree', _publishCurrentSelectedQuestion);
}

$(function () {
    if (!document.querySelector(WIDGET_SELECTOR)) {
        return;
    }
    document.addEventListener('vellum:ready', _initListener, {once: true});
});
