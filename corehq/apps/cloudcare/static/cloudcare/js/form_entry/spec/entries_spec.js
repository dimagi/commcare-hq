'use strict';
/* eslint-env mocha */
/* globals moment */
hqDefine("cloudcare/js/form_entry/spec/entries_spec", function () {
    describe('Entries', function () {
        var constants = hqImport("cloudcare/js/form_entry/const"),
            entries = hqImport("cloudcare/js/form_entry/entries"),
            formUI = hqImport("cloudcare/js/form_entry/form_ui"),
            utils = hqImport("cloudcare/js/utils"),
            questionJSON,
            spy;

        before(function () {
            hqImport("hqwebapp/js/initial_page_data").register(
                "has_geocoder_privs",
                true
            );
            hqImport("hqwebapp/js/initial_page_data").register(
                "toggles_dict",
                {
                    WEB_APPS_UPLOAD_QUESTIONS: true,
                    WEB_APPS_ANCHORED_SUBMIT: false,
                }
            );
        });

        after(function () {
            hqImport("hqwebapp/js/initial_page_data").unregister("toggles_dict");
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
                "help_image": null,
                "help_audio": null,
                "help_video": null,
                "answer": null,
                "datatype": "int",
                "style": {},
                "caption_video": null,
            };
            spy = sinon.spy();
            $.subscribe('formplayer.' + constants.ANSWER, spy);
            this.clock = sinon.useFakeTimers(new Date("2020-03-15 15:41").getTime());
        });

        afterEach(function () {
            $.unsubscribe();
            this.clock.restore();
        });

        it('Should return the IntEntry', function () {
            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.IntEntry);
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

            questionJSON.datatype = constants.SELECT;
            questionJSON.style = { raw: constants.MINIMAL + " dummy" };
            questionJSON.choices = ['a', 'b'];

            entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.DropdownEntry);
            assert.equal(entry.templateType, 'dropdown');
            var options = _.rest(entry.options());      // drop placeholder
            assert.deepEqual(options, [{
                text: 'a',
                id: 1,
            }, {
                text: 'b',
                id: 2,
            }]);

            assert.equal(entry.placeholderText, 'Please choose an item');
            entry.rawAnswer(1);
            this.clock.tick(1000);
            assert.isTrue(spy.calledOnce);
            assert.equal(entry.answer(), 1);

            entry.rawAnswer(2);
            this.clock.tick(1000);
            assert.isTrue(spy.calledTwice);
        });

        it('Should return MultiDropdownEntry', function () {
            var entry;

            questionJSON.datatype = constants.MULTI_SELECT;
            questionJSON.style = { raw: constants.MINIMAL};
            questionJSON.choices = ['a', 'b'];
            questionJSON.answer = [1, 2]; // answer is based on a 1 indexed index of the choices

            entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.MultiDropdownEntry);
            assert.equal(entry.templateType, 'multidropdown');
            assert.equal(entry.placeholderText, 'Please choose an item');

            assert.isTrue(entry instanceof entries.MultiSelectEntry);
            assert.sameMembers(entry.answer(), [1, 2]);
            assert.sameMembers(entry.rawAnswer(), ['a', 'b']);

            entry.answer([1]);
            entry.choices(['a', 'c']);
            this.clock.tick(1000);
            assert.equal(spy.calledOnce, true);
            assert.equal(entry.rawAnswer()[0], 'a');
            assert.equal(entry.answer()[0], 1);
        });

        it('Should retain Dropdown value on options change', function () {
            // This behavior is necessary for changing the in-form language
            var entry,
                question;
            questionJSON.datatype = constants.SELECT;
            questionJSON.style = { raw: constants.MINIMAL };
            questionJSON.choices = ['one', 'two'];
            question = formUI.Question(questionJSON);

            entry = question.entry;
            assert.isTrue(entry instanceof entries.DropdownEntry);

            entry.rawAnswer(2);     // 'two'
            assert.equal(entry.answer(), 2);

            question.choices(['un', 'deux']);
            assert.equal(entry.answer(), 2);
        });

        it('Should return FloatEntry', function () {
            questionJSON.datatype = constants.FLOAT;
            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.FloatEntry);
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
            questionJSON.datatype = constants.SELECT;
            questionJSON.style = { raw: constants.COMBOBOX };
            questionJSON.choices = ['a', 'b'];
            questionJSON.answer = 2;

            entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.ComboboxEntry);
            assert.equal(entry.rawAnswer(), 2);

            entry.rawAnswer(1);
            assert.equal(entry.answer(), 1);

            entry.rawAnswer('');
            assert.equal(entry.answer(), constants.NO_ANSWER);

            entry.rawAnswer(15);
            assert.equal(entry.answer(), constants.NO_ANSWER);
        });

        it('Should retain Combobox value on options change', function () {
            // This behavior is necessary for changing the in-form language
            var entry,
                question;
            questionJSON.datatype = constants.SELECT;
            questionJSON.style = { raw: constants.COMBOBOX };
            questionJSON.choices = ['one', 'two'];
            question = formUI.Question(questionJSON);

            entry = question.entry;
            assert.isTrue(entry instanceof entries.ComboboxEntry);

            entry.rawAnswer(2);     // 'two'
            assert.equal(entry.answer(), 2);

            question.choices(['moja', 'mbili', 'tatu']);
            assert.equal(entry.answer(), 2);
        });

        it('Should properly filter combobox', function () {
            // Standard filter
            assert.isTrue(entries.ComboboxEntry.filter('o', { text: 'one two', id: 1 }, null));
            assert.isFalse(entries.ComboboxEntry.filter('t', { text: 'one two', id: 1 }, null));

            // Multiword filter
            assert.isTrue(
                entries.ComboboxEntry.filter('one three', { text: 'one two three', id: 1 }, constants.COMBOBOX_MULTIWORD)
            );
            assert.isFalse(
                entries.ComboboxEntry.filter('two three', { text: 'one two', id: 1 }, constants.COMBOBOX_MULTIWORD)
            );

            // Fuzzy filter
            assert.isTrue(
                entries.ComboboxEntry.filter('onet', { text: 'onetwo', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isTrue(
                entries.ComboboxEntry.filter('onet', { text: 'onetwothree', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isFalse(
                entries.ComboboxEntry.filter('onwt', { text: 'onetwo', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isTrue(
                entries.ComboboxEntry.filter('OneT', { text: 'onetwo', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isTrue(
                entries.ComboboxEntry.filter('one tt', { text: 'one', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isTrue(
                entries.ComboboxEntry.filter('o', { text: 'one', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isTrue(
                entries.ComboboxEntry.filter('on', { text: 'on', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isTrue(
                entries.ComboboxEntry.filter('three', { text: 'one two three', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isTrue(
                entries.ComboboxEntry.filter('tree', { text: 'one two three', id: 1 }, constants.COMBOBOX_FUZZY)
            );
            assert.isFalse(
                entries.ComboboxEntry.filter('thirty', { text: 'one two three', id: 1 }, constants.COMBOBOX_FUZZY)
            );
        });

        it('Should return FreeTextEntry', function () {
            questionJSON.datatype = constants.STRING;
            questionJSON.style.raw = 'hint-as-placeholder';
            questionJSON.hint = 'this is a hint';
            var entry = formUI.Question(questionJSON).entry;
            entry.setPlaceHolder(entry.useHintAsPlaceHolder());
            assert.isTrue(entry instanceof entries.FreeTextEntry);
            assert.equal(entry.templateType, 'text');
            assert.equal(entry.placeholderText, 'this is a hint');

            entry.answer('harry');
            this.clock.tick(1000);
            assert.isTrue(spy.calledOnce);

            entry.rawAnswer('');
            assert.equal(entry.answer(), constants.NO_ANSWER);
        });

        it('Should return MultiSelectEntry', function () {
            questionJSON.datatype = constants.MULTI_SELECT;
            questionJSON.choices = ['a', 'b'];
            questionJSON.answer = [1]; // answer is based on a 1 indexed index of the choices

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.MultiSelectEntry);
            assert.equal(entry.templateType, 'select');
            assert.sameMembers(entry.answer(), [1]);
            assert.sameMembers(entry.rawAnswer(), ['a']);

            // Did not change answer, do not call change
            entry.rawAnswer(['a']);
            this.clock.tick(1000);
            assert.equal(spy.callCount, 0);
            assert.sameMembers(entry.answer(), [1]);

            entry.rawAnswer(['b']);
            assert.equal(spy.calledOnce, true);
            assert.sameMembers(entry.answer(), [2]);
        });

        it('Should retain MultiSelectEntry when choices change', function () {
            questionJSON.datatype = constants.MULTI_SELECT;
            questionJSON.choices = ['a', 'b'];
            questionJSON.answer = [1, 2]; // answer is based on a 1 indexed index of the choices

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.MultiSelectEntry);
            assert.sameMembers(entry.answer(), [1, 2]);
            assert.sameMembers(entry.rawAnswer(), ['a', 'b']);

            entry.answer([1]);
            entry.choices(['a', 'c']);
            this.clock.tick(1000);
            assert.equal(spy.calledOnce, true);
            assert.sameMembers(entry.rawAnswer(), ['a']);
            assert.sameMembers(entry.answer(), [1]);
        });

        it('Should return SingleSelectEntry', function () {
            questionJSON.datatype = constants.SELECT;
            questionJSON.choices = ['a', 'b'];
            questionJSON.answer = 1;

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.SingleSelectEntry);
            assert.equal(entry.templateType, 'select');
            assert.equal(entry.rawAnswer(), 'a');

            entry.rawAnswer('b');
            this.clock.tick(1000);
            assert.isTrue(spy.calledOnce);
            assert.equal(entry.answer(), 2);
            assert.equal(entry.rawAnswer(), 'b');
        });

        it('Should retain SingleSelect value on choices change with valid value', function () {
            questionJSON.datatype = constants.SELECT;
            questionJSON.choices = ['a', 'b'];
            questionJSON.answer = 1;

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.SingleSelectEntry);
            assert.equal(entry.rawAnswer(), 'a');

            entry.choices(['c', 'a', 'b']);
            entry.answer(2);
            this.clock.tick(1000);
            assert.isTrue(spy.calledOnce);
            assert.equal(entry.answer(), 2);
            assert.equal(entry.rawAnswer(), 'a');
        });

        it('Should retain SingleSelect value on choices change with invalid value', function () {
            questionJSON.datatype = constants.SELECT;
            questionJSON.choices = ['a', 'b'];
            questionJSON.answer = 1;

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.SingleSelectEntry);
            assert.equal(entry.rawAnswer(), 'a');

            entry.choices(['c', 'b']);
            entry.answer(null);
            this.clock.tick(1000);
            assert.isTrue(spy.calledOnce);
            assert.isNull(entry.answer());
            assert.isNull(entry.rawAnswer());
        });

        it('Should return ButtonSelectEntry', function () {
            questionJSON.datatype = constants.SELECT;
            questionJSON.style = { raw: constants.BUTTON_SELECT };
            questionJSON.choices = ['a', 'b'];
            questionJSON.answer = 1;

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.ButtonSelectEntry);
            assert.equal(entry.templateType, 'button');
            assert.equal(entry.rawAnswer(), 'a');
        });

        it('Should cycle through ButtonSelect choices on click', function () {
            questionJSON.datatype = constants.SELECT;
            questionJSON.style = { raw: constants.BUTTON_SELECT };
            questionJSON.choices = ['a', 'b', 'c'];
            questionJSON.answer = 1;

            var entry = formUI.Question(questionJSON).entry;
            // value 'a' shows label 'b' to indicate what will be selected when clicked
            assert.equal(entry.rawAnswer(), 'a');
            assert.equal(entry.buttonLabel(), 'b');

            entry.onClick();
            assert.equal(entry.rawAnswer(), 'b');
            assert.equal(entry.buttonLabel(), 'c');

            entry.onClick();
            assert.equal(entry.rawAnswer(), 'c');
            assert.equal(entry.buttonLabel(), 'a');
        });

        it('Should return DateEntry', function () {
            questionJSON.datatype = constants.DATE;
            questionJSON.answer = '1990-09-26';

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.DateEntry);
            assert.equal(entry.templateType, 'date');

            entry.answer('1987-11-19');
            this.clock.tick(1000);
            assert.isTrue(spy.calledOnce);
        });

        it('Should convert two-digit dates to four-digit dates', function () {
            assert.equal(utils.convertTwoDigitYear("03-04-50"), "03/04/1950");
            assert.equal(utils.convertTwoDigitYear("03-04-28"), "03/04/2028");
            assert.equal(utils.convertTwoDigitYear("3/4/1928"), "3/4/1928");
            assert.equal(utils.convertTwoDigitYear("not-a-date"), "not-a-date");
        });

        it('Should coerce user input dates to moment objects', function () {
            let assertParsesAs = function (userInput, expected) {
                let res = utils.parseInputDate(userInput);
                assert.isTrue(moment.isMoment(res));
                assert.equal(
                    res.toISOString(),
                    moment(expected, "YYYY-MM-DD").toISOString()
                );
            };

            assertParsesAs("03/04/20", "2020-03-04");
            assertParsesAs("3/4/20", "2020-03-04");
            assertParsesAs("2020-03-04", "2020-03-04");
        });

        it('Should fail to interpret invalid date inputs', function () {
            let assertInvalid = function (userInput) {
                assert.isNull(utils.parseInputDate(userInput));
            };

            assertInvalid("23/01/2022");
            assertInvalid("23/1/22");
            assertInvalid("23-1-22");
        });

        it('Should return TimeEntry', function () {
            questionJSON.datatype = constants.TIME;
            questionJSON.answer = '12:30';

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.TimeEntry);
            assert.equal(entry.templateType, 'time');

            entry.rawAnswer('12:45');
            this.clock.tick(1000);
            assert.isTrue(spy.calledOnce);
        });

        it('Should return EthiopanDateEntry', function () {
            questionJSON.datatype = constants.DATE;
            questionJSON.answer = '2021-01-29'; // 2013-05-21 in Ethiopian
            questionJSON.style = { raw: 'ethiopian' };

            var entry = formUI.Question(questionJSON).entry;
            entry.entryId = 'date-entry-ethiopian';
            assert.isTrue(entry instanceof entries.EthiopianDateEntry);
            assert.equal(entry.templateType, 'ethiopian-date');

            entry.afterRender();

            // the date is set correctly to ethiopian
            assert.equal(entry.$picker.calendarsPicker('getDate').toString(), '2013-05-21');

            // select a new date, ensure the correct gregorian date is saved as the answer
            entry.$picker.calendarsPicker('selectDate', $("[title='Select Kidame, Tir 22, 2013']")[0]);
            assert.equal(entry.answer(), '2021-01-30');

            entry.$picker.calendarsPicker('clear');
            assert.equal(entry.answer(), constants.NO_ANSWER);

            this.clock.tick(1000);
            assert.isTrue(spy.calledTwice);
        });

        it('Should return InfoEntry', function () {
            questionJSON.datatype = constants.INFO;
            var entry = formUI.Question(questionJSON).entry;

            assert.isTrue(entry instanceof entries.InfoEntry);
        });

        it('Should return a GeoPointEntry', function () {
            questionJSON.datatype = constants.GEO;
            questionJSON.answer = [1.2, 3.4];

            var entry = formUI.Question(questionJSON).entry;
            assert.equal(entry.answer()[0], 1.2);
            assert.equal(entry.answer()[1], 3.4);

            entry.answer([3,3]);
            this.clock.tick(1000);
            assert.isTrue(spy.calledOnce);

            entry.answer([3,3]); // do not call on same values
            assert.isTrue(spy.calledOnce);
        });

        it('Should return a PhoneEntry', function () {
            questionJSON.datatype = constants.STRING;
            questionJSON.style = { raw: 'numeric' };

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.PhoneEntry);
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
            assert.equal(entry.answer(), constants.NO_ANSWER);
        });

        it('Should return a AddressEntry', function () {
            questionJSON.datatype = constants.STRING;
            questionJSON.style = { raw: constants.ADDRESS };

            var entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.AddressEntry);
        });

        it('Should allow decimals in a PhoneEntry', function () {
            questionJSON.datatype = constants.STRING;
            questionJSON.style = { raw: 'numeric' };

            var entry = formUI.Question(questionJSON).entry;
            entry.rawAnswer('-123.4');
            assert.equal(entry.answer(), '-123.4');

            entry.rawAnswer('-+123');
            assert.isOk(entry.question.error());

            entry.rawAnswer('...123');
            assert.isOk(entry.question.error());
        });

        it('Should return ImageEntry', function () {
            var entry;
            questionJSON.datatype = constants.BINARY;
            questionJSON.control = constants.CONTROL_IMAGE_CHOOSE;

            entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.ImageEntry);
        });

        it('Should return AudioEntry', function () {
            var entry;
            questionJSON.datatype = constants.BINARY;
            questionJSON.control = constants.CONTROL_AUDIO_CAPTURE;

            entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.AudioEntry);
        });

        it('Should return VideoEntry', function () {
            var entry;
            questionJSON.datatype = constants.BINARY;
            questionJSON.control = constants.CONTROL_VIDEO_CAPTURE;

            entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.VideoEntry);
        });

        it('Should return SignatureEntry', function () {
            var entry;
            questionJSON.datatype = constants.BINARY;
            questionJSON.control = constants.CONTROL_IMAGE_CHOOSE;
            questionJSON.style = { raw: constants.SIGNATURE };

            entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.SignatureEntry);
        });

        it('Should return UnsupportedEntry when binary question has an unsupported control', function () {
            var entry;
            questionJSON.datatype = constants.BINARY;
            questionJSON.control = constants.CONTROL_UPLOAD;

            entry = formUI.Question(questionJSON).entry;
            assert.isTrue(entry instanceof entries.UnsupportedEntry);
        });
    });
});
