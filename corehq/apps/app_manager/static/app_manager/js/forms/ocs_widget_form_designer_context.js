import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import ocsContext, {WIDGET_SELECTOR} from "hqwebapp/js/ocs_page_context";

const FORMDESIGNER = '#formdesigner';

function _vellum() {
    return $(FORMDESIGNER).vellum("get");
}

function extractFormXml(vellum) {
    return vellum.createXML({withCaseMappings: true});
}

function extractQuestionTypes(form) {
    const types = {};
    form.walkMugs(function (mug) {
        if (mug.absolutePath && mug.options.typeName) {
            types[mug.absolutePath] = mug.options.typeName;
        }
    });
    return types;
}

function buildSelectedQuestion(mug) {
    if (!mug) {
        return null;
    }
    const parent = mug.parentMug;
    const belongsToQuestion = parent && {
        type: parent.options.typeName,
        label: parent.form.vellum.getMugDisplayName(parent),
        question_id: parent.p.nodeID,
        path: parent.hashtagPath,
    };

    if (mug.__className === "Choice") {
        return {
            type: mug.options.typeName,
            label: mug.form.vellum.getMugDisplayName(mug),
            value: mug.p.nodeID,
            belongs_to_question: belongsToQuestion,
        };
    }
    if (mug.__className === "Itemset") {
        return {
            type: mug.options.typeName,
            label: mug.form.vellum.getMugDisplayName(mug),
            belongs_to_question: belongsToQuestion,
        };
    }
    return {
        type: mug.options.typeName,
        label: mug.form.vellum.getMugDisplayName(mug),
        question_id: mug.p.nodeID,
        path: mug.hashtagPath,
    };
}

function extractSelectedQuestion(vellum) {
    return buildSelectedQuestion(vellum?.getCurrentlySelectedMug());
}

function _collectFormContext() {
    const vellum = _vellum();
    const form = vellum?.data.core.form;
    if (!form) {
        return {};
    }
    return {
        form_context: {
            form_xml: extractFormXml(vellum),
            question_types: extractQuestionTypes(form),
            current_selected_question: extractSelectedQuestion(vellum),
            module_name: initialPageData.get('module_name'),
        },
    };
}

$(function () {
    if (!document.querySelector(WIDGET_SELECTOR)) {
        return;
    }
    ocsContext.registerContextCollector(_collectFormContext);
});

export {extractFormXml, extractQuestionTypes, extractSelectedQuestion};
