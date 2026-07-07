import $ from "jquery";

import VELLUM_OPTIONS from "app_manager/spec/form_designer_context/vellum_options";
import ORPHAN_BIND_XML from "app_manager/spec/form_designer_context/orphan_bind_xml";
import {
    extractFormXml,
    extractQuestionTypes,
    extractSelectedQuestion,
    exportedForTesting,
    unselectedQuestionWarnings,
} from "app_manager/js/forms/ocs_widget_form_designer_context";

const {
    _collectMugErrors,
    _formWarnings,
    _cardListFieldErrors,
    _xpathEditorError,
    _dataSourceWarnings,
} = exportedForTesting;


function bootVellum() {
    return new Promise(function (resolve) {
        const $fd = $('<div/>').appendTo("body");
        let ready = false;
        VELLUM_OPTIONS.core.onReady = function () {
            if (!ready) {
                ready = true;
                resolve({$fd: $fd, vellum: $fd.vellum("get")});
            }
        };
        $fd.vellum(VELLUM_OPTIONS);
    });
}

describe("OCS form designer context extractors", function () {
    this.timeout(20000);

    let $fd, vellum;

    function addQuestion(type, nodeID) {
        const mug = $fd.vellum("addQuestion", type);
        if (nodeID) {
            // Match Vellum's test util
            if (mug.p.labelItext) {
                mug.p.labelItext.set(mug.getLabelValue());
            }
            if (type === "Choice" && mug.p.labelItext) {
                mug.p.labelItext.set(nodeID);
            }
            mug.p.nodeID = nodeID;
        }
        return mug;
    }

    function loadForm(xml) {
        vellum.data.core.parseWarnings = [];
        vellum.loadXML(xml, {});
        delete vellum.data.core.parseWarnings;
        return vellum.data.core.form;
    }

    function clickQuestion(mug) {
        vellum.jstree("deselect_all", true);
        vellum.jstree("select_node", mug.ufid);
        $fd.find(".collapse-toggle.collapsed").click();
        return mug;
    }

    before(async function () {
        ({$fd, vellum} = await bootVellum());
    });

    beforeEach(function () {
        vellum.loadXML("");
    });

    after(function () {
        if (vellum) {
            vellum.destroy();
        }
        $fd.remove();
    });

    describe("extractFormXml", function () {
        it("returns the form XML including its questions", function () {
            addQuestion("Text", "village_name");

            const xml = extractFormXml(vellum);

            assert.isString(xml);
            assert.include(xml, 'nodeset="/data/village_name"');
        });
    });

    describe("extractQuestionTypes", function () {
        it("maps each mug's absolute path to its Vellum type name", function () {
            addQuestion("Text", "first_name");
            addQuestion("Int", "age");

            const types = extractQuestionTypes(vellum.data.core.form);

            assert.equal(types["/data/first_name"], "Text");
            assert.equal(types["/data/age"], "Integer");
        });

        it("excludes control-only mugs (choices, lookup tables) that have no path", function () {
            addQuestion("Select", "color");
            addQuestion("Choice", "red");

            const types = extractQuestionTypes(vellum.data.core.form);

            assert.equal(types["/data/color"], "Multiple Choice");
            assert.notProperty(types, "null");
        });
    });

    describe("extractSelectedQuestion", function () {
        it("returns null when nothing is selected", function () {
            vellum.data.core.$tree.jstree("deselect_all");

            assert.isNull(extractSelectedQuestion(vellum));
        });

        it("builds the shape for the selected question", function () {
            const mug = addQuestion("Text", "patient_name");
            vellum.setCurrentMug(mug);

            assert.deepEqual(extractSelectedQuestion(vellum), {
                type: "Text",
                label: vellum.getMugDisplayName(mug),
                question_id: "patient_name",
                path: mug.hashtagPath,
            });
        });

        it("builds the shape for a selected choice and its parent question", function () {
            const select = addQuestion("Select", "color");
            const choice = addQuestion("Choice", "red");
            vellum.setCurrentMug(choice);

            assert.deepEqual(extractSelectedQuestion(vellum), {
                type: "Choice",
                label: vellum.getMugDisplayName(choice),
                value: "red",
                belongs_to_question: {
                    type: "Multiple Choice",
                    label: vellum.getMugDisplayName(select),
                    question_id: "color",
                    path: select.hashtagPath,
                },
            });
        });
    });

    describe("Form designer's error context", function () {
        it("_collectMugErrors reads mug.messages", function () {
            const mug = addQuestion("Text", "age");
            mug.p.nodeID = "invalid id";
            mug.validate();

            assert.deepEqual(_collectMugErrors(mug), [{
                field: mug.spec.nodeID.lstring,
                value: "invalid id",
                error: "invalid id is not a valid Question ID. " +
                    "It must start with a letter and contain only " +
                    "letters, numbers, and '-' or '_' characters.",
            }]);
        });

        it("unselectedQuestionWarnings walks mugs and collects errors from unselected questions", function () {
            const first = addQuestion("Text", "first");
            first.p.nodeID = "invalid id";
            first.validate();
            const second = addQuestion("Text", "second");

            const select = addQuestion("Select", "color");
            addQuestion("Choice", "red");
            const dupRed = addQuestion("Choice", "red");
            dupRed.validate();

            assert.equal(dupRed.__className, "Choice");
            assert.isNull(dupRed.absolutePath);
            assert.equal(dupRed.parentMug, select);

            const result = unselectedQuestionWarnings(vellum.data.core.form, second.ufid);

            const invalidIdError = "invalid id is not a valid Question ID. " +
                "It must start with a letter and contain only " +
                "letters, numbers, and '-' or '_' characters.";

            assert.property(result, first.absolutePath);
            assert.equal(result[first.absolutePath][0].error, invalidIdError);
            assert.notProperty(result, second.absolutePath);

            const choiceKey = `${select.absolutePath}/${dupRed.p.nodeID}`;
            assert.property(result, choiceKey);
            assert.deepEqual(result[choiceKey], [{
                field: dupRed.spec.nodeID.lstring,
                value: "red",
                error: "This choice value has been used in the same question",
            }]);
        });

        it("_formWarnings reads form.errors", function () {
            const form = loadForm(ORPHAN_BIND_XML);
            assert.deepEqual(_formWarnings(form), [
                "Bind Node [/data/ghost] found but has no associated Data node. " +
                "This bind node will be discarded!",
            ]);
        });

        it("_xpathEditorError captures the open xpath editor's validation error", async function () {
            const mug = addQuestion("Text", "q");
            clickQuestion(mug);

            vellum.data.core.currentlyEditedProperty = "relevantAttr";
            vellum.displayXPathEditor({
                mug: mug,
                xpathType: "bool",
                value: "this is not valid!!!",
                change: function () {},
                done: function () {},
            });
            // displayXPathEditor dynamically imports expressionEditor
            // so the save button isn't in the DOM immediately.
            for (let i = 0; i < 100 && !$fd.find(".fd-xpath-save-button").length; i++) {
                await new Promise(r => setTimeout(r, 50));
            }

            $fd.find(".fd-xpath-save-button").first().click();

            const result = _xpathEditorError(mug, $fd[0]);
            assert.equal(result.length, 1);
            assert.equal(result[0].field, "Display Condition - XPath Editor");
            assert.include(result[0].error, "Lexical error");
            assert.include(result[0].value, "this is not valid");
        });

        it("_cardListFieldErrors collects a cardList row error", function () {
            const stc = addQuestion("SaveToCase", "stc");
            stc.p.case_id = "uuid()";
            stc.p.useCreate = true;
            stc.p.case_type = "patient";
            stc.p.caseName = "/data/name";
            stc.p.createProperty = {
                "bad name!": {calculate: "'x'"},
            };
            clickQuestion(stc);

            const result = _cardListFieldErrors(stc, $fd[0]);
            assert.equal(result.length, 1);
            assert.equal(result[0].field, stc.spec.createProperty.lstring);
            assert.equal(result[0].subfield, "Property Name");
            assert.equal(result[0].value, "bad name!");
            assert.include(result[0].error, "letters, numbers, '-' and '_'");
        });

        it("_dataSourceWarnings reads the databrowser banner after a datasources load failure", function () {
            const $banner = $fd.find(".fd-external-sources-error");
            assert.isTrue($banner.hasClass("hide"));

            vellum.datasources.fire({
                type: "error",
                xhr: {status: 400, responseText: "boom"},
            });

            assert.isFalse($banner.hasClass("hide"));
            const warnings = _dataSourceWarnings($fd[0]);
            assert.equal(warnings.length, 1);
            assert.include(warnings[0], "Could not load app properties");
            assert.include(warnings[0], "boom");
        });
    });
});
