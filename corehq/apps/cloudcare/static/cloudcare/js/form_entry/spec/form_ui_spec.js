import _ from "underscore";
import sinon from "sinon/pkg/sinon";
import initialPageData from "hqwebapp/js/initial_page_data";
import constants from "cloudcare/js/form_entry/const";
import formUI from "cloudcare/js/form_entry/form_ui";
import * as fixtures from "cloudcare/js/form_entry/spec/fixtures";

describe('Fullform formUI', function () {
    var questionJSON,
        formJSON,
        groupJSON,
        noQuestionGroupJSON,
        nestedGroupJSON,
        spy;

    before(function () {
        initialPageData.register(
            "toggles_dict",
            {
                WEB_APPS_UPLOAD_QUESTIONS: true,
                WEB_APPS_ANCHORED_SUBMIT: false,
            },
        );
    });

    after(function () {
        initialPageData.unregister("toggles_dict");
    });

    beforeEach(function () {
        questionJSON = fixtures.selectJSON();

        groupJSON = fixtures.groupJSON();

        noQuestionGroupJSON = fixtures.noQuestionGroupJSON();

        nestedGroupJSON = {
            tree: [groupJSON, noQuestionGroupJSON],
            seq_id: 1,
            exists: true,
            session_id: '123',
            title: 'My title',
            langs: ['en'],
        };

        formJSON = {
            tree: [questionJSON, groupJSON],
            seq_id: 1,
            session_id: '123',
            title: 'My title',
            langs: ['en'],
        };

        spy = sinon.spy();
        $.subscribe('formplayer.' + constants.ANSWER, spy);
        this.clock = sinon.useFakeTimers();

    });

    afterEach(function () {
        $.unsubscribe();
        this.clock.restore();
    });

    it('Should render a basic form and reconcile', function () {
        var form = formUI.Form(formJSON),
            newJson = [questionJSON];

        assert.equal(form.children().length, 2);

        form.fromJS({ children: newJson });
        assert.equal(form.children().length, 1);
    });

    it('Should render questions grouped by row', function () {
        let styleObj = {raw: '2-per-row'};
        let q0 = fixtures.textJSON({
            style: styleObj,
            ix: "0",
        });
        let g0 = fixtures.groupJSON({
            ix: "1",
        });
        g0.children[0].children[0].style = styleObj;
        g0.children[0].children[1].style = styleObj;
        let q1 = fixtures.selectJSON({
            style: styleObj,
            ix: "2",
        });
        let q2 = fixtures.labelJSON({
            style: styleObj,
            ix: "3",
        });
        let q3 = fixtures.labelJSON({
            style: styleObj,
            ix: "4",
        });
        formJSON.tree = [q0, g0, q1, q2, q3];
        let form = formUI.Form(formJSON);

        // Expected structure (where ge signifies type "grouped-element-tile-row")
        assert.equal(form.children().length, 4); // [ge, g, ge, ge]
        assert.equal(form.children()[0].children().length, 1); // [q0]
        assert.equal(form.children()[1].children()[0].children()[0].children()[0].children()[0].children().length, 2); // [q(ix=2,3), q(ix=2,4)]
        assert.equal(form.children()[2].children().length, 2); // [q1, q2]
        assert.equal(form.children()[3].children().length, 1); // [q3]
    });

    it('Should render groups and question grouped by row', function () {
        let styleObj = {raw: '3-per-row'};
        let styleObj2 = {raw: '2-per-row'};

        let g0 = fixtures.groupJSON({
            style: styleObj,
            ix: "0",
        });
        let g1 = fixtures.groupJSON({
            style: styleObj,
            ix: "1",
        });
        let q2 = fixtures.labelJSON({
            style: styleObj,
            ix: "3",
        });

        g0.children[0].children[0].style = styleObj2;
        g0.children[0].children[1].style = styleObj2;

        formJSON.tree = [g0,g1,q2];
        let form = formUI.Form(formJSON);

        /* Group-Element-Tile-Row
                -Group
                    -Group-Element-Tile-Row
                        -Group
                            -Group-Element-Tile-Row
                                -Question
                                -Question
                -Group
                    -Group-Element-Tile-Row
                        -Group
                            -Group-Element-Tile-Row
                                -Question
                            -Group-Element-Tile-Row
                                -Question
                -Question
        */

        // Expected structure (where ge signifies type "grouped-element-tile-row")
        assert.equal(form.children().length, 1); // [ge]
        assert.equal(form.children()[0].children().length, 3); // [g0,g1,q2]
        assert.equal(form.children()[0].children()[0].children().length, 1); // [ge]
        assert.equal(form.children()[0].children()[0].children()[0].children().length, 1); // [group]
        assert.equal(form.children()[0].children()[0].children()[0].children()[0].children().length, 1); // [ge]
        assert.equal(form.children()[0].children()[0].children()[0].children()[0].children()[0].children().length, 2); // [q,q]

        assert.equal(form.children()[0].children()[1].children().length, 1); // [ge]
        assert.equal(form.children()[0].children()[1].children()[0].children().length, 1); // [group]
        assert.equal(form.children()[0].children()[1].children()[0].children()[0].children().length, 2); // [ge,ge]
        assert.equal(form.children()[0].children()[1].children()[0].children()[0].children()[0].children().length, 1); // [q]
        assert.equal(form.children()[0].children()[1].children()[0].children()[0].children()[1].children().length, 1); // [q]
    });

    it('Should calculate nested background header color', function () {
        let styleObj = {raw: 'group-collapse'};
        let g0 = fixtures.groupJSON({
            style: styleObj,
        });
        let g1 = fixtures.groupJSON({
            style: styleObj,
        });
        let g2 = fixtures.groupJSON({
            style: styleObj,
        });
        g1.children[0].style = styleObj;
        g2.children[0].children[0].style = styleObj;
        g1.children[0].children.push(g2);
        g0.children[0].children.push(g1);

        /* Group (collapsible) [g0]
            -Group-Element-Tile-Row
                -Group [g0-0]
                    -Group-Element-Tile-Row
                        -Question
                    -Group-Element-Tile-Row
                        -Question
                    -Group-Element-Tile-Row
                        -Group (collapsible) [g1]
                            -Group-Element-Tile-Row
                                -Group (collapsible) [g1-0]
                                    -Group-Element-Tile-Row
                                        -Question
                                    -Group-Element-Tile-Row
                                        -Question
                                    -Group-Element-Tile-Row
                                        -Group (collapsible) [g2-0]
                                            -Group-Element-Tile-Row
                                                -Question
                                            -Group-Element-Tile-Row
                                                -Question
                */
        formJSON.tree = [g0];
        let form = formUI.Form(formJSON);

        assert.equal(form.children()[0].children()[0].headerBackgroundColor(), '#002f71'); //[g0]
        assert.equal(form.children()[0].children()[0].children()[0].children()[0].headerBackgroundColor(), ''); //[g0-0]
        assert.equal(form.children()[0].children()[0].children()[0].children()[0].children()[2].children()[0].headerBackgroundColor(), '#003e96'); //[g1]
        assert.equal(form.children()[0].children()[0].children()[0].children()[0].children()[2].children()[0].children()[0].children()[0].headerBackgroundColor(), '#004EBC'); //[g1-0]
        assert.equal(form.children()[0].children()[0].children()[0].children()[0].children()[2].children()[0].children()[0].children()[0].children()[2].children()[0].headerBackgroundColor(), '#002f71'); //[r1]
        assert.equal(form.children()[0].children()[0].children()[0].children()[0].children()[2].children()[0].children()[0].children()[0].children()[2].children()[0].children()[0].children()[0].headerBackgroundColor(), ''); //[r1-0]
    });

    it('Should reconcile question choices', function () {
        formJSON.tree = [questionJSON];
        var form = formUI.Form(formJSON),
            question = form.children()[0].children()[0];
        assert.equal(form.children().length, 1);
        assert.equal(question.choices().length, 2);

        questionJSON.choices = ['A new choice'];
        formJSON.tree = [questionJSON];
        form.fromJS(formJSON);
        assert.equal(form.children().length, 1);
        assert.equal(question.choices().length, 1);
    });

    it('Should reconcile a GeoPointEntry', function () {
        questionJSON.datatype = constants.GEO;
        questionJSON.answer = null;
        formJSON.tree = [questionJSON];
        var form = formUI.Form(_.clone(formJSON)),
            question = form.children()[0].children()[0];
        assert.equal(question.answer(), null);

        questionJSON.answer = [1,2];
        formJSON.tree = [questionJSON];
        $.publish('session.reconcile', [_.clone(formJSON), question]);
        assert.sameMembers(question.answer(), [1,2]);

        questionJSON.answer = [3,3];
        form = formUI.Form(_.clone(formJSON)),
        question = form.children()[0].children()[0];
        $.publish('session.reconcile', [_.clone(formJSON), question]);
        assert.sameMembers(question.answer(), [3,3]);
    });

    it('Should reconcile a FileInput entry', function () {
        questionJSON.datatype = constants.BINARY;
        questionJSON.control = constants.CONTROL_IMAGE_CHOOSE;
        questionJSON.answer = "chucknorris.png";
        formJSON.tree = [questionJSON];
        var form = formUI.Form(_.clone(formJSON)),
            question = form.children()[0].children()[0];
        assert.equal(question.answer(), "chucknorris.png");

        // simulate response processing from FP
        question.pendingAnswer(_.clone(question.answer()));
        question.formplayerMediaRequest = {state: () => "resolved"};
        question.entry.file({name: "chucknorris.png"});
        questionJSON.answer = "autogenerated.png";
        formJSON.tree = [questionJSON];
        $.publish('session.reconcile', [_.clone(formJSON), question]);
        assert.equal(question.answer(), "autogenerated.png");
    });

    it('Should only subscribe once', function () {
        /**
         * This specifically ensures that we unsubscribe from events when we change forms
         */
        var formJSON2 = {};
        $.extend(formJSON2, formJSON);
        var form = formUI.Form(formJSON),
            form2 = formUI.Form(formJSON2),
            spy = sinon.spy(),
            spy2 = sinon.spy();

        sinon.stub(form, 'fromJS').callsFake(spy);
        sinon.stub(form2, 'fromJS').callsFake(spy2);

        $.publish('session.reconcile', [{}, formUI.Question(questionJSON, form)]);
        assert.isFalse(spy.calledOnce);
        assert.isTrue(spy2.calledOnce);
    });


    it('Should throttle answers', function () {
        questionJSON.datatype = constants.STRING;
        var question = formUI.Question(questionJSON);
        question.answer('abc');
        this.clock.tick(question.throttle);
        assert.equal(spy.callCount, 1);

        question.answer('abcd');
        this.clock.tick(question.throttle - 10);
        assert.equal(spy.callCount, 1);
        this.clock.tick(10);
        assert.equal(spy.callCount, 2);
    });

    it('Should not be valid if question has serverError', function () {
        questionJSON.datatype = constants.STRING;
        var question = formUI.Question(questionJSON);

        question.serverError('Answer required');
        assert.isFalse(question.isValid());

        question.serverError(null);
        assert.isTrue(question.isValid());

    });

    it('Should handle a constraint error', function () {
        var form = formUI.Form(formJSON);
        var question = formUI.Question(questionJSON, form);

        assert.equal(question.serverError(), null);
        $.publish('session.reconcile', [{
            "reason": null,
            "type": "constraint",
            "seq_id": 2,
            "status": "validation-error",
        }, question]);

        assert.isOk(question.serverError());
    });

    it('Should find nested questions', function () {
        var form = formUI.Form(nestedGroupJSON);
        assert.isTrue(form.children()[0].children()[0].hasAnyNestedQuestions());
        assert.isFalse(form.children()[1].children()[0].hasAnyNestedQuestions());

        groupJSON.children = [questionJSON];
        formJSON.tree = [groupJSON];
        let form2 = formUI.Form(formJSON);
        assert.isTrue(form2.children()[0].hasAnyNestedQuestions());
    });

    it('Should not reconcile outdated data', function () {
        // Check that we don't overwrite a question value if the value is changed while
        // an 'answer' request is in flight

        questionJSON.answer = "first answer";
        formJSON.tree = [questionJSON];
        var form = formUI.Form(_.clone(formJSON)),
            question = form.children()[0].children()[0];
        assert.equal(question.answer(), "first answer");

        // question is updated
        question.pendingAnswer("updated answer");

        // response from first 'answer' request is received
        questionJSON.answer = "first answer";
        formJSON.tree = [questionJSON];
        $.publish('session.reconcile', [_.clone(formJSON), question]);

        // value should still be the updated value
        assert.equal(question.answer(), "updated answer");
    });
});

describe('formUI.removeSiblingsOfRepeatGroup', function () {
    it('should do nothing for an empty root node', function () {
        const rootNode = {children: []};
        formUI.removeSiblingsOfRepeatGroup(rootNode, '1');
        assert.deepEqual(rootNode, {children: []});
    });

    it('should remove nodes with the same prefix and keep the rest', function () {
        const rootNode = {
            children: [
                {ix: '0'},
                {ix: '1_0'},
                {ix: '1_1'},
            ],
        };
        formUI.removeSiblingsOfRepeatGroup(rootNode, '1_1');
        assert.deepEqual(
            rootNode,
            {
                children: [
                    {ix: '0'},
                ],
            });
    });

    it('should keep other repeat groups', function () {
        const rootNode = {
            children: [
                {ix: '0_0'},
                {ix: '1_0'},
                {ix: '1_1'},
                {ix: '2_1'},
            ],
        };
        formUI.removeSiblingsOfRepeatGroup(rootNode, '1_1');
        assert.deepEqual(
            rootNode,
            {
                children: [
                    {ix: '0_0'},
                    {ix: '2_1'},
                ],
            });
    });

    it('should work with nested children', function () {
        const rootNode = {
            children: [
                {ix: '0'},
                {
                    ix: '1',
                    children: [
                        {ix: '1,0_0'},
                        {ix: '1,0_1'},
                        {ix: '1,1'},
                    ],
                },
            ],
        };
        formUI.removeSiblingsOfRepeatGroup(rootNode, '1,0_1');
        assert.deepEqual(
            rootNode,
            {
                children: [
                    {ix: '0'},
                    {
                        ix: '1',
                        children: [
                            {ix: '1,1'},
                        ],
                    },
                ],
            });
    });
});
