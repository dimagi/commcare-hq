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

function _isVisible(elem) {
    return elem && elem.offsetParent !== null;
}

function _toSingleLine(text) {
    return text ? text.replace(/\s+/g, ' ').trim() : '';
}

function _collectMugErrors(mug) {
    const spec = mug.spec;
    const result = [];
    mug.messages.each((msg, attr) => {
        if (msg.level === 'info') {return;}
        const field = attr ? (spec[attr]?.lstring || attr) : '';
        // mug.p[attr] isn't always a string (booleans, itext objects)
        const value = attr && typeof mug.p[attr] === 'string' ? mug.p[attr] : '';
        result.push({
            ...(field && {field}),
            ...(value && {value}),
            error: mug.messages.getMessageText(msg.message),
        });
    });
    return result;
}

function _cardListFieldErrors(mug, fd) {
    // `.fd-field-error` is cardList-only and lives only in the DOM.
    const out = [];
    fd.querySelectorAll('.fd-card-list .has-error').forEach(row => {
        const attr = row.closest('[name^="property-"]').getAttribute('name').slice('property-'.length);
        const field = mug.spec[attr].lstring;

        const subfield = row.querySelector('label')?.textContent;

        const input = row.querySelector('.form-control');
        const value = input.value || input.textContent || '';

        const error = row.querySelector('.fd-field-error').textContent;

        out.push({
            ...(field && {field}),
            ...(subfield && {subfield}),
            ...(value && {value}),
            error,
        });
    });
    return out;
}

function _xpathEditorError(mug, fd) {
    const elem = fd.querySelector('.fd-xpath-validation-summary');
    if (!_isVisible(elem)) {return [];}
    const editedProp = mug.form.vellum.data.core.currentlyEditedProperty;

    const input = fd.querySelector('.fd-xpath-editor-text');
    const expression = _toSingleLine(input.value || input.textContent);

    const error = _toSingleLine(elem.querySelector('pre').textContent);

    return [{
        field: `${mug.spec[editedProp].lstring} - XPath Editor`,
        value: expression,
        error,
    }];
}

function selectedQuestionWarnings(mug, fd) {
    return [
        ..._collectMugErrors(mug),
        ..._cardListFieldErrors(mug, fd),
        ..._xpathEditorError(mug, fd),
    ];
}

function unselectedQuestionWarnings(form, selectedUfid) {
    const warnings = {};
    form.walkMugs(mug => {
        if (mug.ufid === selectedUfid) {return;}
        const mugWarnings = _collectMugErrors(mug);
        if (!mugWarnings.length) {return;}

        if (mug.absolutePath) {
            warnings[mug.absolutePath] = mugWarnings;
            return;
        }

        // Choices/Lookup tables have no path of their own
        const parent = mug.parentMug;
        if (!parent?.absolutePath) {return;}
        const key = `${parent.absolutePath}/${mug.p.nodeID || mug.options.typeName}`;
        warnings[key] = mugWarnings;
    });
    return warnings;
}

function _formWarnings(form) {
    const errors = form.errors.filter(err => err.level === 'error');
    const formWarnings = [...errors];
    const parseWarnings = form.errors.filter(err => err.level === 'parse-warning');
    // Only the latest parse warning is displayed in the UI
    if (parseWarnings.length) {
        formWarnings.push(parseWarnings[parseWarnings.length - 1]);
    }
    return formWarnings.map(err => err.message.trim());
}

function _dataSourceWarnings(fd) {
    // External data source load failures only exist as a DOM banner.
    const banner = fd.querySelector('.fd-external-sources-error');
    if (!_isVisible(banner)) {return [];}
    return [banner.querySelector('.help-block').textContent.trim()];
}

function formLoadWarnings(form, fd) {
    return [..._formWarnings(form), ..._dataSourceWarnings(fd)];
}

function _collectFormContext() {
    const vellum = _vellum();
    const form = vellum?.data.core.form;
    if (!form) {
        return {};
    }
    const fd = document.querySelector(FORMDESIGNER);
    const selectedMug = vellum.getCurrentlySelectedMug();
    const currentSelectedQuestion = buildSelectedQuestion(selectedMug);
    if (currentSelectedQuestion) {
        currentSelectedQuestion.warnings = selectedQuestionWarnings(selectedMug, fd);
    }
    return {
        form_context: {
            form_xml: extractFormXml(vellum),
            question_types: extractQuestionTypes(form),
            unselected_question_warnings: unselectedQuestionWarnings(form, selectedMug?.ufid),
            form_load_warnings: formLoadWarnings(form, fd),
            current_selected_question: currentSelectedQuestion,
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

export {
    extractFormXml,
    extractQuestionTypes,
    extractSelectedQuestion,
    unselectedQuestionWarnings,
};

export const exportedForTesting = {
    _collectMugErrors,
    _formWarnings,
    _cardListFieldErrors,
    _xpathEditorError,
    _dataSourceWarnings,
};
