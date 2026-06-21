import $ from "jquery";

import {
    extractFormXml,
    extractQuestionTypes,
    extractSelectedQuestion,
} from "app_manager/js/forms/ocs_widget_form_designer_context";

// Minimum options to boot the bundled Vellum
const VELLUM_OPTIONS = {
    core: {
        loadDelay: 0,
        formName: "Test Form",
        dataSourcesEndpoint: function (callback) { callback([]); },
        saveUrl: function () {},
    },
    javaRosa: {
        langs: ["en"],
        displayLanguage: "en",
    },
    features: {
        disable_popovers: true,
    },
    intents: {
        templates: [{id: "intent", name: "Intent", mime: "text/plain"}],
    },
};

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
            mug.p.nodeID = nodeID;
        }
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
            assert.include(xml, '<bind nodeset="/data/village_name" type="xsd:string" />');
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
                value: "red",
                belongs_to_question: {
                    type: "Multiple Choice",
                    question_id: "color",
                    path: select.hashtagPath,
                },
            });
        });
    });
});
