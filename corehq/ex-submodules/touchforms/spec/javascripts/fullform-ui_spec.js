describe('Fullform UI', function() {
    var questionJSON,
        answerSpy,
        formSpec,
        formJSON,
        sessionData,
        spy,
        repeatJSON,
        repeatNestJSON;

    beforeEach(function() {
        formSpec = {
            "type": "url",
            "val": "http://dummy/dummy.xml"
        };
        questionJSON = {
            "caption_audio": null,
            "caption": "Do you want to modify the visit number?",
            "binding": "/data/start/update_visit_count",
            "caption_image": null,
            "type": "question",
            "caption_markdown": null,
            "required": 0,
            "ix": "1,2",
            "relevant": 1,
            "help": null,
            "answer": null,
            "datatype": "select",
            "style": {},
            "caption_video": null,
            "choices": [
                "Yes",
                "No"
            ]
        };

        repeatJSON = {
            "caption_audio": null,
            "caption": "Repeater",
            "caption_image": null,
            "type": "repeat-juncture",
            "caption_markdown": null,
            "ix": "0J",
            "relevant": 1,
            "main-header": "Repeater",
            "children": [],
            "add-choice": "None - Add Repeater",
            "caption_video": null
        };

        repeatNestJSON = {
            "caption_audio": null,
            "caption": "Repeat Simple",
            "caption_image": null,
            "type": "repeat-juncture",
            "caption_markdown": null,
            "ix": "0J",
            "relevant": 1,
            "children": [{
                "caption": "Repeat Simple 1/1",
                "type": "sub-group",
                "uuid": "ed3f01b37034",
                "ix": "0:0",
                "children": [{
                    "caption_audio": null,
                    "caption": "Text_Question",
                    "binding": "/data/repeat/Text_Question",
                    "caption_image": null,
                    "type": "question",
                    "caption_markdown": null,
                    "required": 0,
                    "ix": "0:0,0",
                    "relevant": 1,
                    "help": null,
                    "answer": null,
                    "datatype": "str",
                    "style": {},
                    "caption_video": null
                }],
                "repeatable": 1
            }],
            "add-choice": "Add another Repeat Simple",
            "header": "Repeat Simple",
            "caption_video": null
        };

        formJSON = {
            tree: [questionJSON, repeatJSON],
            seq_id: 1,
            session_id: '123',
            title: 'My title',
            langs: ['en']
        };

        sessionData = {
            "username": "ben",
            "additional_filters": {
                "footprint": true
            },
            "domain": "mydomain",
            "user_id": "123",
            "user_data": {},
            "app_id": "456",
            "session_name": "SUCCEED CM app > CM4 - Clinic Visit - Benjamin",
            "app_version": "2.0",
            "device_id": "cloudcare",
            "host": "http://dummy"
        };
        spy = sinon.spy();
        $.subscribe('formplayer.' + Formplayer.Const.ANSWER, spy);
        this.clock = sinon.useFakeTimers();

    });

    afterEach(function() {
        $.unsubscribe();
        this.clock.restore();
    });

    it('Should render a basic form and reconcile', function() {
        var form = new Form(formJSON),
            newJson = [questionJSON];

        expect(form.children().length).toBe(2);

        form.fromJS({ children: newJson });
        expect(form.children().length).toBe(1);
    });

    it('Should render a repeater question', function() {
        formJSON.tree = [repeatJSON];
        var form = new Form(formJSON);
        expect(form.children().length).toBe(1);
        expect(form.children()[0].children().length).toBe(0);

        // Add new repeat
        form.fromJS({ children: [repeatNestJSON] });
        expect(form.children().length).toBe(1);
        // Each repeat is a group with questions
        expect(form.children()[0].type()).toBe(Formplayer.Const.REPEAT_TYPE);
        expect(form.children()[0].children().length).toBe(1);
        expect(form.children()[0].children()[0].type()).toBe(Formplayer.Const.GROUP_TYPE);
        expect(form.children()[0].children()[0].isRepetition).toBe(true);
        expect(form.children()[0].children()[0].children()[0].type())
            .toBe(Formplayer.Const.QUESTION_TYPE);
    });

    it('Should reconcile question choices', function() {
        formJSON.tree = [questionJSON];
        var form = new Form(formJSON),
            question = form.children()[0];
        expect(form.children().length).toBe(1);
        expect(question.choices().length).toBe(2);

        questionJSON.choices = ['A new choice'];
        formJSON.tree = [questionJSON];
        form.fromJS(formJSON);
        expect(form.children().length).toBe(1);
        expect(question.choices().length).toBe(1);
    });

    it('Should reconcile a GeoPointEntry', function() {
        questionJSON.datatype = Formplayer.Const.GEO;
        questionJSON.answer = null;
        formJSON.tree = [questionJSON];
        var form = new Form(_.clone(formJSON)),
            question = form.children()[0];
        expect(question.answer()).toBe(null);

        questionJSON.answer = [1,2];
        formJSON.tree = [questionJSON];
        $.publish('session.reconcile', [_.clone(formJSON), question]);
        expect(question.answer()).toEqual([1,2]);

        questionJSON.answer = [3,3];
        formJSON.tree = [questionJSON];
        $.publish('session.reconcile', [_.clone(formJSON), question]);
        expect(question.answer()).toEqual([3,3]);
    });

    it('Should only subscribe once', function() {
        /**
         * This specifically ensures that we unsubscribe from events when we change forms
         */
        var formJSON2 = {};
        $.extend(formJSON2, formJSON);
        var form = new Form(formJSON),
            form2 = new Form(formJSON2),
            spy = sinon.spy();
            spy2 = sinon.spy();

        sinon.stub(form, 'fromJS', spy);
        sinon.stub(form2, 'fromJS', spy2);

        $.publish('session.reconcile', [{}, new Question(questionJSON, form)]);
        expect(spy.calledOnce).toBe(false);
        expect(spy2.calledOnce).toBe(true);
    });


    it('Should throttle answers', function() {
        questionJSON.datatype = Formplayer.Const.STRING;
        var question = new Question(questionJSON);
        question.answer('abc');
        this.clock.tick(question.throttle);
        expect(spy.callCount).toBe(1);

        question.answer('abcd');
        this.clock.tick(question.throttle - 10);
        expect(spy.callCount).toBe(1);
        this.clock.tick(10);
        expect(spy.callCount).toBe(2);
    });

    it('Should not be valid if question has serverError', function() {
        questionJSON.datatype = Formplayer.Const.STRING;
        var question = new Question(questionJSON);

        question.serverError('Answer required');
        expect(question.isValid()).toBe(false);

        question.serverError(null);
        expect(question.isValid()).toBe(true);

    });

    it('Should handle a constraint error', function() {
        var form = new Form(formJSON);
        var question = new Question(questionJSON, form);

        expect(question.serverError()).toBe(null);
        $.publish('session.reconcile', [{
            "reason": null,
            "type": "constraint",
            "seq_id": 2,
            "status": "validation-error"
        }, question]);

        expect(question.serverError()).toBeTruthy();
    });
});
