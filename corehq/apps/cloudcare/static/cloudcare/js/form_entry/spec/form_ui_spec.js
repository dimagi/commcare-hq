/* eslint-env mocha */
hqDefine("cloudcare/js/form_entry/spec/form_ui_spec", function () {
    describe('Fullform formUI', function () {
        var constants = hqImport("cloudcare/js/form_entry/const"),
            formUI = hqImport("cloudcare/js/form_entry/form_ui"),
            fixtures = hqImport("cloudcare/js/form_entry/spec/fixtures"),
            questionJSON,
            formJSON,
            groupJSON,
            noQuestionGroupJSON,
            nestedGroupJSON,
            spy,
            repeatJSON,
            repeatNestJSON;

        beforeEach(function () {
            questionJSON = fixtures.selectJSON();

            repeatJSON = fixtures.repeatJSON();

            repeatNestJSON = fixtures.repeatNestJSON();

            groupJSON = fixtures.groupJSON();

            noQuestionGroupJSON = fixtures.noQuestionGroupJSON();

            nestedGroupJSON = {
                tree: [groupJSON, noQuestionGroupJSON],
                seq_id: 1,
                session_id: '123',
                title: 'My title',
                langs: ['en'],
            };

            formJSON = {
                tree: [questionJSON, repeatJSON],
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

        it('Should render a repeater question', function () {
            formJSON.tree = [repeatJSON];
            var form = formUI.Form(formJSON);
            assert.equal(form.children().length, 1);
            assert.equal(form.children()[0].children().length, 0);

            // Add new repeat
            form.fromJS({ children: [repeatNestJSON] });
            assert.equal(form.children().length, 1);
            // Each repeat is a group with questions
            assert.equal(form.children()[0].type(), constants.REPEAT_TYPE);
            assert.equal(form.children()[0].children().length, 1);
            assert.equal(form.children()[0].children()[0].type(), constants.GROUP_TYPE);
            assert.isTrue(form.children()[0].children()[0].isRepetition);
            assert.equal(form.children()[0].children()[0].children()[0].type(), constants.GROUPED_QUESTION_TILE_ROW_TYPE);
            assert.equal(form.children()[0].children()[0].children()[0].children()[0].type(), constants.QUESTION_TYPE);
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
            g0.children[0].children[0].style = styleObj;
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

            // Expected structure (where gq signifies type "grouped-question-tile-row")
            assert.equal(form.children().length, 4); // [gq, g, gq, gq]
            assert.equal(form.children()[0].children().length, 1); // [q0]
            assert.equal(form.children()[1].children()[0].children().length, 2); // [q(ix=2,3), q(ix=2,4)]
            assert.equal(form.children()[2].children().length, 2); // [q1, q2]
            assert.equal(form.children()[3].children().length, 1); // [q3]
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
            question.formplayerProcessed = true;
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
            assert.isTrue(form.children()[0].hasAnyNestedQuestions());
            assert.isFalse(form.children()[1].hasAnyNestedQuestions());
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
});
