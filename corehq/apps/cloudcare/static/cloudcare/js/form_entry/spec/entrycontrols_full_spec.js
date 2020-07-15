/* eslint-env mocha */
/* globals Question, DropdownEntry, ComboboxEntry, Formplayer */

describe('Entries', function () {
    var questionJSON,
        spy;


    beforeEach(function () {
        window.MAPBOX_ACCESS_TOKEN = 'xxx';
        questionJSON = {
            "caption_audio": null,
            "caption": "Do you want to modify the visit number?",
            "binding": "/data/start/update_visit_count",
            "caption_image": null,
            "type": "question",
            "caption_markdown": null,
            "required": 0,
            "ix": "0",
            "relevant": 1,
            "help": null,
            "answer": null,
            "datatype": "int",
            "style": {},
            "caption_video": null,
        };
        spy = sinon.spy();
        $.subscribe('formplayer.' + Formplayer.Const.ANSWER, spy);
        this.clock = sinon.useFakeTimers();
    });

    afterEach(function () {
        $.unsubscribe();
        this.clock.restore();
    });

    it('Should return the IntEntry', function () {
        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof IntEntry);
        assert.equal(entry.templateType, 'str');

        entry.rawAnswer('1234');
        valid = entry.isValid('1234');
        assert.isTrue(valid);
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), 1234);

        valid = entry.isValid('abc');
        assert.isFalse(valid);
    });

    it('Should return DropdownEntry', function () {
        var entry;

        questionJSON.datatype = Formplayer.Const.SELECT;
        questionJSON.style = { raw: Formplayer.Const.MINIMAL };
        questionJSON.choices = ['a', 'b'];

        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof DropdownEntry);
        assert.equal(entry.templateType, 'dropdown');
        assert.deepEqual(entry.options(), [{
            text: 'a',
            idx: 1,
        }, {
            text: 'b',
            idx: 2,
        }]);

        entry.rawAnswer(1);
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), 1);

        entry.rawAnswer(2);
        this.clock.tick(1000);
        assert.isTrue(spy.calledTwice);
    });

    it('Should return FloatEntry', function () {
        questionJSON.datatype = Formplayer.Const.FLOAT;
        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof FloatEntry);
        assert.equal(entry.templateType, 'str');

        entry.rawAnswer('2.3');
        valid = entry.isValid('2.3');
        assert.isTrue(valid);
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), 2.3);

        entry.rawAnswer('2.4');
        this.clock.tick(1000);
        assert.isTrue(spy.calledTwice);

        valid = entry.isValid('mouse');
        assert.isFalse(valid);
    });

    it('Should return ComboboxEntry', function () {
        var entry;
        questionJSON.datatype = Formplayer.Const.SELECT;
        questionJSON.style = { raw: Formplayer.Const.COMBOBOX };
        questionJSON.choices = ['a', 'b'];
        questionJSON.answer = 2;

        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof ComboboxEntry);
        assert.equal(entry.rawAnswer(), 'b');

        entry.rawAnswer('a');
        assert.equal(entry.answer(), 1);

        entry.rawAnswer('');
        assert.equal(entry.answer(), Formplayer.Const.NO_ANSWER);

        entry.rawAnswer('abc');
        assert.equal(entry.answer(), Formplayer.Const.NO_ANSWER);
    });

    it('Should validate Combobox properly', function () {
        var entry,
            question;
        questionJSON.datatype = Formplayer.Const.SELECT;
        questionJSON.style = { raw: Formplayer.Const.COMBOBOX };
        questionJSON.choices = ['a', 'b'];
        question = new Question(questionJSON);

        entry = question.entry;
        assert.isTrue(entry instanceof ComboboxEntry);

        entry.rawAnswer('a');
        assert.equal(entry.answer(), 1);

        question.choices(['c', 'd']);
        assert.isFalse(entry.isValid(entry.rawAnswer()));
        assert.isTrue(!!question.error());
    });

    it('Should properly filter combobox', function () {
        // Standard filter
        assert.isTrue(ComboboxEntry.filter('o', { name: 'one two', id: 1 }, null));
        assert.isFalse(ComboboxEntry.filter('t', { name: 'one two', id: 1 }, null));

        // Multiword filter
        assert.isTrue(
            ComboboxEntry.filter('one three', { name: 'one two three', id: 1 }, Formplayer.Const.COMBOBOX_MULTIWORD)
        );
        assert.isFalse(
            ComboboxEntry.filter('two three', { name: 'one two', id: 1 }, Formplayer.Const.COMBOBOX_MULTIWORD)
        );

        // Fuzzy filter
        assert.isTrue(
            ComboboxEntry.filter('onet', { name: 'onetwo', id: 1 }, Formplayer.Const.COMBOBOX_FUZZY)
        );
        assert.isTrue(
            ComboboxEntry.filter('OneT', { name: 'onetwo', id: 1 }, Formplayer.Const.COMBOBOX_FUZZY)
        );
        assert.isFalse(
            ComboboxEntry.filter('one tt', { name: 'one', id: 1 }, Formplayer.Const.COMBOBOX_FUZZY)
        );
        assert.isTrue(
            ComboboxEntry.filter('o', { name: 'one', id: 1 }, Formplayer.Const.COMBOBOX_FUZZY)
        );
        assert.isTrue(
            ComboboxEntry.filter('on', { name: 'on', id: 1 }, Formplayer.Const.COMBOBOX_FUZZY)
        );
    });

    it('Should return FreeTextEntry', function () {
        questionJSON.datatype = Formplayer.Const.STRING;
        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof FreeTextEntry);
        assert.equal(entry.templateType, 'text');

        entry.answer('harry');
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);

        entry.rawAnswer('');
        assert.equal(entry.answer(), Formplayer.Const.NO_ANSWER);
    });

    it('Should return MultiSelectEntry', function () {
        questionJSON.datatype = Formplayer.Const.MULTI_SELECT;
        questionJSON.choices = ['a', 'b'];
        questionJSON.answer = [1]; // answer is based on a 1 indexed index of the choices

        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof MultiSelectEntry);
        assert.equal(entry.templateType, 'select');
        assert.sameMembers(entry.answer(), [1]);
        assert.sameMembers(entry.rawAnswer(), [1]);

        // Did not change answer, do not call change
        entry.rawAnswer([1]);
        this.clock.tick(1000);
        assert.equal(spy.callCount, 0);
        assert.sameMembers(entry.answer(), [1]);

        entry.rawAnswer([2]);
        assert.equal(spy.calledOnce, true);
        assert.sameMembers(entry.answer(), [2]);
    });

    it('Should return SingleSelectEntry', function () {
        questionJSON.datatype = Formplayer.Const.SELECT;
        questionJSON.choices = ['a', 'b'];
        questionJSON.answer = 1;

        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof SingleSelectEntry);
        assert.equal(entry.templateType, 'select');
        assert.equal(entry.rawAnswer(), 1);

        entry.rawAnswer(2);
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), 2);
    });

    it('Should return DateEntry', function () {
        questionJSON.datatype = Formplayer.Const.DATE;
        questionJSON.answer = '1990-09-26';

        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof DateEntry);
        assert.equal(entry.templateType, 'date');

        entry.answer('1987-11-19');
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
    });

    it('Should return TimeEntry', function () {
        questionJSON.datatype = Formplayer.Const.TIME;
        questionJSON.answer = '12:30';

        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof TimeEntry);
        assert.equal(entry.templateType, 'time');

        entry.rawAnswer('12:45');
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
    });

    it('Should return InfoEntry', function () {
        questionJSON.datatype = Formplayer.Const.INFO;
        entry = (new Question(questionJSON)).entry;

        assert.isTrue(entry instanceof InfoEntry);
    });

    it('Should return a GeoPointEntry', function () {
        questionJSON.datatype = Formplayer.Const.GEO;
        questionJSON.answer = [1.2, 3.4];

        entry = (new Question(questionJSON)).entry;
        assert.equal(entry.answer()[0], 1.2);
        assert.equal(entry.answer()[1], 3.4);

        entry.answer([3,3]);
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);

        entry.answer([3,3]); // do not call on same values
        assert.isTrue(spy.calledOnce);
    });

    it('Should return a PhoneEntry', function () {
        questionJSON.datatype = Formplayer.Const.STRING;
        questionJSON.style = { raw: 'numeric' };

        entry = (new Question(questionJSON)).entry;
        assert.isTrue(entry instanceof PhoneEntry);
        assert.equal(entry.answer(), null);
        assert.equal(entry.templateType, 'str');

        entry.rawAnswer('1234');
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), '1234');

        entry.rawAnswer('abc'); // Invalid entry should not answer question
        assert.isTrue(spy.calledOnce);
        assert.isOk(entry.question.error());

        entry.rawAnswer('');
        assert.equal(entry.answer(), Formplayer.Const.NO_ANSWER);
    });

    it('Should allow decimals in a PhoneEntry', function () {
        questionJSON.datatype = Formplayer.Const.STRING;
        questionJSON.style = { raw: 'numeric' };

        entry = (new Question(questionJSON)).entry;
        entry.rawAnswer('-123.4');
        assert.equal(entry.answer(), '-123.4');

        entry.rawAnswer('-+123');
        assert.isOk(entry.question.error());

        entry.rawAnswer('...123');
        assert.isOk(entry.question.error());
    });
});
