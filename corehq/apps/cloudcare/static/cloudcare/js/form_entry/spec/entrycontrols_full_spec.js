/* eslint-env mocha */

describe('Entries', function () {
    var Const = hqImport("cloudcare/js/form_entry/const"),
        Controls = hqImport("cloudcare/js/form_entry/entrycontrols_full"),
        UI = hqImport("cloudcare/js/form_entry/form_ui"),
        questionJSON,
        spy;

    before(function () {
        hqImport("hqwebapp/js/initial_page_data").register(
            "has_geocoder_privs",
            true
        );
    });

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
        $.subscribe('formplayer.' + Const.ANSWER, spy);
        this.clock = sinon.useFakeTimers();
    });

    afterEach(function () {
        $.unsubscribe();
        this.clock.restore();
    });

    it('Should return the IntEntry', function () {
        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.IntEntry);
        assert.equal(entry.templateType, 'str');

        entry.rawAnswer('1234');
        assert.isTrue(entry.isValid('1234'));
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), 1234);
        assert.isFalse(entry.isValid('abc'));
    });

    it('Should return DropdownEntry', function () {
        var entry;

        questionJSON.datatype = Const.SELECT;
        questionJSON.style = { raw: Const.MINIMAL };
        questionJSON.choices = ['a', 'b'];

        entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.DropdownEntry);
        assert.equal(entry.templateType, 'dropdown');
        var options = _.rest(entry.options());      // drop placeholder
        assert.deepEqual(options, [{
            text: 'a',
            id: 1,
        }, {
            text: 'b',
            id: 2,
        }]);

        entry.rawAnswer(1);
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), 1);

        entry.rawAnswer(2);
        this.clock.tick(1000);
        assert.isTrue(spy.calledTwice);
    });

    it('Should retain Dropdown value on options change', function () {
        // This behavior is necessary for changing the in-form language
        var entry,
            question;
        questionJSON.datatype = Const.SELECT;
        questionJSON.style = { raw: Const.MINIMAL };
        questionJSON.choices = ['one', 'two'];
        question = UI.Question(questionJSON);

        entry = question.entry;
        assert.isTrue(entry instanceof Controls.DropdownEntry);

        entry.rawAnswer(2);     // 'two'
        assert.equal(entry.answer(), 2);

        question.choices(['un', 'deux']);
        assert.equal(entry.answer(), 2);
    });

    it('Should return FloatEntry', function () {
        questionJSON.datatype = Const.FLOAT;
        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.FloatEntry);
        assert.equal(entry.templateType, 'str');

        entry.rawAnswer('2.3');
        assert.isTrue(entry.isValid('2.3'));
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), 2.3);

        entry.rawAnswer('2.4');
        this.clock.tick(1000);
        assert.isTrue(spy.calledTwice);
        assert.isFalse(entry.isValid('mouse'));
    });

    it('Should return ComboboxEntry', function () {
        var entry;
        questionJSON.datatype = Const.SELECT;
        questionJSON.style = { raw: Const.COMBOBOX };
        questionJSON.choices = ['a', 'b'];
        questionJSON.answer = 2;

        entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.ComboboxEntry);
        assert.equal(entry.rawAnswer(), 2);

        entry.rawAnswer(1);
        assert.equal(entry.answer(), 1);

        entry.rawAnswer('');
        assert.equal(entry.answer(), Const.NO_ANSWER);

        entry.rawAnswer(15);
        assert.equal(entry.answer(), Const.NO_ANSWER);
    });

    it('Should retain Combobox value on options change', function () {
        // This behavior is necessary for changing the in-form language
        var entry,
            question;
        questionJSON.datatype = Const.SELECT;
        questionJSON.style = { raw: Const.COMBOBOX };
        questionJSON.choices = ['one', 'two'];
        question = UI.Question(questionJSON);

        entry = question.entry;
        assert.isTrue(entry instanceof Controls.ComboboxEntry);

        entry.rawAnswer(2);     // 'two'
        assert.equal(entry.answer(), 2);

        question.choices(['moja', 'mbili', 'tatu']);
        assert.equal(entry.answer(), 2);
    });

    it('Should properly filter combobox', function () {
        // Standard filter
        assert.isTrue(Controls.ComboboxEntry.filter('o', { text: 'one two', id: 1 }, null));
        assert.isFalse(Controls.ComboboxEntry.filter('t', { text: 'one two', id: 1 }, null));

        // Multiword filter
        assert.isTrue(
            Controls.ComboboxEntry.filter('one three', { text: 'one two three', id: 1 }, Const.COMBOBOX_MULTIWORD)
        );
        assert.isFalse(
            Controls.ComboboxEntry.filter('two three', { text: 'one two', id: 1 }, Const.COMBOBOX_MULTIWORD)
        );

        // Fuzzy filter
        assert.isTrue(
            Controls.ComboboxEntry.filter('onet', { text: 'onetwo', id: 1 }, Const.COMBOBOX_FUZZY)
        );
        assert.isTrue(
            Controls.ComboboxEntry.filter('OneT', { text: 'onetwo', id: 1 }, Const.COMBOBOX_FUZZY)
        );
        assert.isFalse(
            Controls.ComboboxEntry.filter('one tt', { text: 'one', id: 1 }, Const.COMBOBOX_FUZZY)
        );
        assert.isTrue(
            Controls.ComboboxEntry.filter('o', { text: 'one', id: 1 }, Const.COMBOBOX_FUZZY)
        );
        assert.isTrue(
            Controls.ComboboxEntry.filter('on', { text: 'on', id: 1 }, Const.COMBOBOX_FUZZY)
        );
    });

    it('Should return FreeTextEntry', function () {
        questionJSON.datatype = Const.STRING;
        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.FreeTextEntry);
        assert.equal(entry.templateType, 'text');

        entry.answer('harry');
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);

        entry.rawAnswer('');
        assert.equal(entry.answer(), Const.NO_ANSWER);
    });

    it('Should return MultiSelectEntry', function () {
        questionJSON.datatype = Const.MULTI_SELECT;
        questionJSON.choices = ['a', 'b'];
        questionJSON.answer = [1]; // answer is based on a 1 indexed index of the choices

        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.MultiSelectEntry);
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
        questionJSON.datatype = Const.SELECT;
        questionJSON.choices = ['a', 'b'];
        questionJSON.answer = 1;

        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.SingleSelectEntry);
        assert.equal(entry.templateType, 'select');
        assert.equal(entry.rawAnswer(), 1);

        entry.rawAnswer(2);
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
        assert.equal(entry.answer(), 2);
    });

    it('Should return DateEntry', function () {
        questionJSON.datatype = Const.DATE;
        questionJSON.answer = '1990-09-26';

        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.DateEntry);
        assert.equal(entry.templateType, 'date');

        entry.answer('1987-11-19');
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
    });

    it('Should return TimeEntry', function () {
        questionJSON.datatype = Const.TIME;
        questionJSON.answer = '12:30';

        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.TimeEntry);
        assert.equal(entry.templateType, 'time');

        entry.rawAnswer('12:45');
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);
    });

    it('Should return EthiopanDateEntry', function () {
        questionJSON.datatype = Const.DATE;
        questionJSON.answer = '2021-01-29'; // 2013-05-21 in Ethiopian
        questionJSON.style = { raw: 'ethiopian' };

        var entry = UI.Question(questionJSON).entry;
        entry.entryId = 'date-entry-ethiopian';
        assert.isTrue(entry instanceof Controls.EthiopianDateEntry);
        assert.equal(entry.templateType, 'ethiopian-date');

        entry.afterRender();

        // the date is set correctly to ethiopian
        assert.equal(entry.$picker.calendarsPicker('getDate').toString(), '2013-05-21');

        // select a new date, ensure the correct gregorian date is saved as the answer
        entry.$picker.calendarsPicker('selectDate', $("[title='Select Kidame, Tir 22, 2013']")[0]);
        assert.equal(entry.answer(), '2021-01-30');

        entry.$picker.calendarsPicker('clear');
        assert.equal(entry.answer(), Const.NO_ANSWER);

        this.clock.tick(1000);
        assert.isTrue(spy.calledTwice);
    });

    it('Should return InfoEntry', function () {
        questionJSON.datatype = Const.INFO;
        var entry = UI.Question(questionJSON).entry;

        assert.isTrue(entry instanceof Controls.InfoEntry);
    });

    it('Should return a GeoPointEntry', function () {
        questionJSON.datatype = Const.GEO;
        questionJSON.answer = [1.2, 3.4];

        var entry = UI.Question(questionJSON).entry;
        assert.equal(entry.answer()[0], 1.2);
        assert.equal(entry.answer()[1], 3.4);

        entry.answer([3,3]);
        this.clock.tick(1000);
        assert.isTrue(spy.calledOnce);

        entry.answer([3,3]); // do not call on same values
        assert.isTrue(spy.calledOnce);
    });

    it('Should return a PhoneEntry', function () {
        questionJSON.datatype = Const.STRING;
        questionJSON.style = { raw: 'numeric' };

        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.PhoneEntry);
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
        assert.equal(entry.answer(), Const.NO_ANSWER);
    });

    it('Should return a AddressEntry', function () {
        questionJSON.datatype = Const.STRING;
        questionJSON.style = { raw: Const.ADDRESS };

        var entry = UI.Question(questionJSON).entry;
        assert.isTrue(entry instanceof Controls.AddressEntry);
    });

    it('Should allow decimals in a PhoneEntry', function () {
        questionJSON.datatype = Const.STRING;
        questionJSON.style = { raw: 'numeric' };

        var entry = UI.Question(questionJSON).entry;
        entry.rawAnswer('-123.4');
        assert.equal(entry.answer(), '-123.4');

        entry.rawAnswer('-+123');
        assert.isOk(entry.question.error());

        entry.rawAnswer('...123');
        assert.isOk(entry.question.error());
    });
});
