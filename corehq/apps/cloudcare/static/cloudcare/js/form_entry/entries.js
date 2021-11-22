/* globals moment, MapboxGeocoder, DOMPurify */
hqDefine("cloudcare/js/form_entry/entries", function () {
    var Const = hqImport("cloudcare/js/form_entry/const"),
        Utils = hqImport("cloudcare/js/form_entry/utils"),
        initialPageData = hqImport("hqwebapp/js/initial_page_data");

    /**
     * The base Object for all entries. Each entry takes a question object
     * @param {Object} question - A question object
     */
    function Entry(question) {
        var self = this;
        self.question = question;
        self.answer = question.answer;
        self.datatype = question.datatype();
        self.entryId = _.uniqueId(this.datatype);

        // Returns true if the rawAnswer is valid, false otherwise
        self.isValid = function (rawAnswer) {
            return self.getErrorMessage(rawAnswer) === null;
        };

        // Returns an error message given the answer. null if no error
        self.getErrorMessage = function () {
            return null;
        };

        self.clear = function () {
            self.answer(Const.NO_ANSWER);
        };
        self.afterRender = function () {
            // Override with any logic that comes after rendering the Entry
        };
        if (self.answer) {
            self.answer.subscribe(self.onAnswerChange.bind(self));
        }
    }
    Entry.prototype.onAnswerChange = function () {};

    // This should set the answer value if the answer is valid. If the raw answer is valid, this
    // function performs any sort of processing that needs to be done before setting the answer.
    Entry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            this.answer(newValue);
        }
        this.question.error(this.getErrorMessage(newValue));
    };

    /**
     * Serves as the base for all entries that take an array answer.
     */
    function EntryArrayAnswer(question, options) {
        var self = this;
        Entry.call(self, question);
        self.rawAnswer = ko.observableArray(_.clone(question.answer()));

        self.rawAnswer.subscribe(self.onPreProcess.bind(self));
        self.previousAnswer = self.answer();
    }
    EntryArrayAnswer.prototype = Object.create(Entry.prototype);
    EntryArrayAnswer.prototype.constructor = Entry;
    EntryArrayAnswer.prototype.onAnswerChange = function () {
        if (Utils.answersEqual(this.answer(), this.previousAnswer)) {
            return;
        }
        this.question.onchange();
        this.previousAnswer = this.answer();
    };
    EntryArrayAnswer.prototype.onPreProcess = function (newValue) {
        var processed;
        if (this.isValid(newValue)) {
            if (newValue.length) {
                processed = _.map(newValue, function (d) { return +d; });
            } else {
                processed = Const.NO_ANSWER;
            }

            if (!Utils.answersEqual(processed, this.answer())) {
                this.previousAnswer = this.answer();
                this.answer(processed);
            }
        }
        self.previousAnswer = null;
    };


    /**
     * Serves as the base for all entries that take an answer that is not an array.
     */
    function EntrySingleAnswer(question, options) {
        var self = this;

        var getRawAnswer = function (answer) {
            // Zero is a perfectly valid answer
            if (answer !== 0 && !answer) {
                return Const.NO_ANSWER;
            }
            return answer;
        };

        Entry.call(self, question);
        self.valueUpdate = undefined;
        self.rawAnswer = ko.observable(getRawAnswer(question.answer()));
        self.placeholderText = '';

        self.rawAnswer.subscribe(self.onPreProcess.bind(self));

        if (options.enableAutoUpdate) {
            self.valueUpdate = 'keyup';
            self.answer.extend({
                rateLimit: {
                    timeout: Const.KO_ENTRY_TIMEOUT,
                    method: "notifyWhenChangesStop",
                },
            });
        }
    }
    EntrySingleAnswer.prototype = Object.create(Entry.prototype);
    EntrySingleAnswer.prototype.constructor = Entry;
    EntrySingleAnswer.prototype.onAnswerChange = function () {
        this.question.onchange();
    };
    EntrySingleAnswer.prototype.enableReceiver = function (question, options) {
        var self = this;
        if (options.receiveStyle) {
            var match = options.receiveStyle.match(/receive-(.*)-(.*)/);
            if (match) {
                var receiveTopic = match[1];
                var receiveTopicField = match[2];
                question.parentPubSub.subscribe(function (message) {
                    if (message === Const.NO_ANSWER) {
                        self.rawAnswer(Const.NO_ANSWER);
                    } else if (message) {
                        self.receiveMessage(message, receiveTopicField);
                    }
                }, null, receiveTopic);
            }
        }
    };
    EntrySingleAnswer.prototype.receiveMessage = function (message, field) {
        // Default implementation, if field is in message register answer.
        var self = this;
        if (message[field]) {
            self.rawAnswer(message[field]);
        } else {
            self.rawAnswer(Const.NO_ANSWER);
        }
    };


    /**
     * An entry that represent a question label.
     */
    function InfoEntry(question) {
        var self = this;
        Entry.call(self, question);
        self.templateType = 'blank';
    }

    InfoEntry.prototype = Object.create(Entry.prototype);
    InfoEntry.prototype.constructor = Entry;


    /**
     * The entry used when we have an unidentified entry
     */
    function UnsupportedEntry(question) {
        var self = this;
        Entry.call(self, question);
        self.templateType = 'unsupported';
        self.answer('Not Supported by Web Entry');
    }
    UnsupportedEntry.prototype = Object.create(Entry.prototype);
    UnsupportedEntry.prototype.constructor = Entry;

    /**
     * The entry that represents a free text input
     */
    function FreeTextEntry(question, options) {
        var self = this;
        EntrySingleAnswer.call(self, question, options);
        var isPassword = ko.utils.unwrapObservable(question.control) === Const.CONTROL_SECRET;
        if (isPassword) {
            self.templateType = 'password';
        } else {
            self.templateType = 'text';
        }
        self.datatype = question.datatype();
        self.domain = question.domain ? question.domain() : 'full';
        self.lengthLimit = options.lengthLimit || 100000;
        self.prose = question.domain_meta ? question.domain_meta().longtext : false;

        self.isValid = function (rawAnswer) {
            var errmsg = self.getErrorMessage(rawAnswer);
            if (errmsg) {
                return false;
            }
            return true;
        };

        self.getErrorMessage = function () {
            return null;
        };

        self.helpText = function () {
            if (isPassword) {
                return gettext('Password');
            }
            switch (self.datatype) {
                case Const.BARCODE:
                    return gettext('Barcode');
                default:
                    return gettext('Free response');
            }
        };
        self.enableReceiver(question, options);
    }
    FreeTextEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    FreeTextEntry.prototype.constructor = EntrySingleAnswer;
    FreeTextEntry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            this.answer(newValue === '' ? Const.NO_ANSWER : newValue);
        }
        this.question.error(this.getErrorMessage(newValue));
    };


    /**
     * The entry that represents an address entry.
     * Takes in a `broadcastStyles` list of strings in format `broadcast-<topic>` to broadcast
     * the address item that is selected. Item contains `full`, `street`, `city`, `us_state`, `us_state_long`,
     * `zipcode`, `country`, `country_short`, `region`.
     */
    function AddressEntry(question, options) {
        var self = this;
        FreeTextEntry.call(self, question, options);
        self.templateType = 'address';
        self.broadcastTopics = [];
        self.editing = true;

        // Callback for the geocoder when an address item is selected. We intercept here and broadcast to
        // subscribers.
        self.geocoderItemCallback = function (item) {
            self.rawAnswer(item.place_name);
            self.editing = false;
            self.broadcastTopics.forEach(function (broadcastTopic) {
                var broadcastObj = Utils.getBroadcastObject(item);
                question.parentPubSub.notifySubscribers(broadcastObj, broadcastTopic);
            });
            // The default full address returned to the search bar
            return item.place_name;
        };

        // geocoder function called when user presses 'x', broadcast a no answer to subscribers.
        self.geocoderOnClearCallback = function () {
            self.rawAnswer(Const.NO_ANSWER);
            self.question.error(null);
            self.editing = true;
            self.broadcastTopics.forEach(function (broadcastTopic) {
                question.parentPubSub.notifySubscribers(Const.NO_ANSWER, broadcastTopic);
            });
        };

        self.afterRender = function () {
            if (options.broadcastStyles) {
                options.broadcastStyles.forEach(function (broadcast) {
                    var match = broadcast.match(/broadcast-(.*)/);
                    if (match) {
                        self.broadcastTopics.push(match[1]);
                    }
                });
            }

            Utils.renderMapboxInput(
                self.entryId,
                self.geocoderItemCallback,
                self.geocoderOnClearCallback,
                initialPageData
            );
        };

        self._inputOnKeyDown = function (event) {
            // On key down, switch to editing mode so we unregister an answer.
            if (!self.editing && self.rawAnswer() !== event.target.value) {
                self.rawAnswer(Const.NO_ANSWER);
                self.question.error('Please select an address from the options');
                self.editing = true;
            }
        };
    }
    AddressEntry.prototype = Object.create(FreeTextEntry.prototype);
    AddressEntry.prototype.constructor = FreeTextEntry;

    /**
     * The entry that defines an integer input. Only accepts whole numbers
     */
    function IntEntry(question, options) {
        var self = this;
        FreeTextEntry.call(self, question, options);
        self.templateType = 'str';
        self.lengthLimit = options.lengthLimit || Const.INT_LENGTH_LIMIT;
        var valueLimit = options.valueLimit || Const.INT_VALUE_LIMIT;

        self.getErrorMessage = function (rawAnswer) {
            if (isNaN(+rawAnswer) || +rawAnswer !== Math.floor(+rawAnswer)) {
                return gettext("Not a valid whole number");
            }
            if (+rawAnswer > valueLimit) {
                return gettext("Number is too large");
            }
            return null;
        };

        self.helpText = function () {
            return gettext('Number');
        };

        self.enableReceiver(question, options);
    }
    IntEntry.prototype = Object.create(FreeTextEntry.prototype);
    IntEntry.prototype.constructor = FreeTextEntry;

    IntEntry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            if (newValue === '') {
                this.answer(Const.NO_ANSWER);
            } else {
                this.answer(+newValue);
            }
        }
        this.question.error(this.getErrorMessage(newValue));
    };

    function PhoneEntry(question, options) {
        FreeTextEntry.call(this, question, options);
        this.templateType = 'str';
        this.lengthLimit = options.lengthLimit;

        this.getErrorMessage = function (rawAnswer) {
            if (rawAnswer === '') {
                return null;
            }
            return (!(/^[+-]?\d*(\.\d+)?$/.test(rawAnswer)) ? "This does not appear to be a valid phone/numeric number" : null);
        };

        this.helpText = function () {
            return gettext('Phone number or Numeric ID');
        };

        this.enableReceiver(question, options);
    }
    PhoneEntry.prototype = Object.create(FreeTextEntry.prototype);
    PhoneEntry.prototype.constructor = FreeTextEntry;


    /**
     * The entry that defines an float input. Only accepts real numbers
     */
    function FloatEntry(question, options) {
        IntEntry.call(this, question, options);
        this.templateType = 'str';
        this.lengthLimit = options.lengthLimit || Const.FLOAT_LENGTH_LIMIT;
        var valueLimit = options.valueLimit || Const.FLOAT_VALUE_LIMIT;

        this.getErrorMessage = function (rawAnswer) {
            if (isNaN(+rawAnswer)) {
                return gettext("Not a valid number");
            }
            if (+rawAnswer > valueLimit) {
                return gettext("Number is too large");
            }
            return null;
        };

        this.helpText = function () {
            return gettext('Decimal');
        };
    }
    FloatEntry.prototype = Object.create(IntEntry.prototype);
    FloatEntry.prototype.constructor = IntEntry;

    /**
     * Represents a checked box entry.
     */
    function MultiSelectEntry(question, options) {
        var self = this;
        EntryArrayAnswer.call(this, question, options);
        self.templateType = 'select';
        self.choices = question.choices;
        self.isMulti = true;

        self.onClear = function () {
            self.rawAnswer([]);
        };

        self.isValid = function (rawAnswer) {
            return _.isArray(rawAnswer);
        };
    }
    MultiSelectEntry.prototype = Object.create(EntryArrayAnswer.prototype);
    MultiSelectEntry.prototype.constructor = EntryArrayAnswer;

    /**
     * Represents a select2 for multiple options
     */
    function MultiDropdownEntry(question, options) {
        var self = this;
        MultiSelectEntry.call(this, question, options);
        self.templateType = 'multidropdown';
        self.placeholderText = gettext('Please choose an item');

        self.helpText = function () {
            return "";
        };

        self.options = ko.computed(function () {
            return _.map(question.choices(), function (choice, idx) {
                return {
                    text: choice,
                    id: idx + 1,
                };
            });
        });

        self.afterRender = function () {
            select2ify(self, {});
        };
    }
    MultiDropdownEntry.prototype = Object.create(MultiSelectEntry.prototype);
    MultiDropdownEntry.prototype.constructor = MultiSelectEntry;
    MultiDropdownEntry.prototype.onAnswerChange = select2AnswerChange(MultiSelectEntry);

    /**
     * Represents multiple radio button entries
     */
    function SingleSelectEntry(question, options) {
        var self = this;
        EntrySingleAnswer.call(this, question, options);
        self.choices = question.choices;
        self.templateType = 'select';
        self.isMulti = false;
        self.onClear = function () {
            self.rawAnswer(Const.NO_ANSWER);
        };
        self.isValid = function () {
            return true;
        };

        self.enableReceiver(question, options);
    }
    SingleSelectEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    SingleSelectEntry.prototype.constructor = EntrySingleAnswer;
    SingleSelectEntry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            if (newValue === Const.NO_ANSWER) {
                this.answer(newValue);
            } else {
                this.answer(+newValue);
            }
        }
    };
    SingleSelectEntry.prototype.receiveMessage = function (message, field) {
        // Iterate through choices and select the one that matches the message[field]
        var self = this;
        if (message[field]) {
            var choices = self.choices();
            for (var i = 0; i < choices.length; i++) {
                if (choices[i] === message[field]) {
                    self.rawAnswer(i + 1);
                    return;
                }
            }
        }
        // either field is not in message or message[field] is not an option.
        self.rawAnswer(Const.NO_ANSWER);
    };

    /**
     * Represents the label part of a Combined Multiple Choice question in a Question List
     */
    function ChoiceLabelEntry(question, options) {
        var self = this;
        EntrySingleAnswer.call(this, question, options);
        self.choices = question.choices;
        self.templateType = 'choice-label';

        self.hideLabel = ko.observable(options.hideLabel);

        self.colStyle = ko.computed(function () {
            // Account for number of choices plus column for clear button
            var colWidth = parseInt(12 / (self.choices().length + 1)) || 1;
            return 'col-xs-' + colWidth;
        });

        self.onClear = function () {
            self.rawAnswer(Const.NO_ANSWER);
        };
        self.isValid = function () {
            return true;
        };
    }
    ChoiceLabelEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    ChoiceLabelEntry.prototype.constructor = EntrySingleAnswer;
    ChoiceLabelEntry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            if (newValue === Const.NO_ANSWER) {
                this.answer(newValue);
            } else {
                this.answer(+newValue);
            }
        }
    };

    /**
     *  For dropdowns, each option is assigned an id, which is its index,
     *  with the first option given index 1. Both the entry's answer and
     *  rawAnswer contain this index value.
     */
    function DropdownEntry(question, options) {
        var self = this;
        EntrySingleAnswer.call(this, question, options);
        self.templateType = 'dropdown';
        self.placeholderText = gettext('Please choose an item');

        self.helpText = function () {
            return "";
        };

        self.options = ko.computed(function () {
            return [{text: "", id: undefined}].concat(_.map(question.choices(), function (choice, idx) {
                return {
                    text: choice,
                    id: idx + 1,
                };
            }));
        });

        self.additionalSelect2Options = function () {
            return {};
        };

        self.afterRender = function () {
            select2ify(self, self.additionalSelect2Options());
        };
    }
    DropdownEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    DropdownEntry.prototype.constructor = EntrySingleAnswer;
    DropdownEntry.prototype.onAnswerChange = select2AnswerChange(EntrySingleAnswer);
    DropdownEntry.prototype.onPreProcess = function (newValue) {
        // When newValue is undefined it means we've unset the select question.
        if (newValue === Const.NO_ANSWER || newValue === undefined) {
            this.answer(Const.NO_ANSWER);
        } else {
            this.answer(+newValue);
        }
    };

    /**
     * The ComboboxEntry is an advanced android formatting entry. It is enabled
     * when the user specifies combobox in the appearance attributes for a
     * single select question.
     *
     * It uses the same UI as the dropdown, but a different matching algorithm.
     *
     * Docs: https://confluence.dimagi.com/display/commcarepublic/Advanced+CommCare+Android+Formatting#AdvancedCommCareAndroidFormatting-SingleSelect"ComboBox"
     */
    function ComboboxEntry(question, options) {
        var self = this;
        DropdownEntry.call(this, question, options);

        // Specifies the type of matching we will do when a user types a query
        self.matchType = options.matchType;

        self.helpText = function () {
            return gettext('Combobox');
        };

        self.additionalSelect2Options = function () {
            return {
                matcher: function (params, option) {
                    var query = $.trim(params.term);
                    if (ComboboxEntry.filter(query, option, self.matchType)) {
                        return option;
                    } else {
                        return null;
                    }
                },
            };
        };

        self.enableReceiver(question, options);
    }

    ComboboxEntry.filter = function (query, option, matchType) {
        if (!query || !option.text) {
            return true;
        }
        query = query.toLowerCase();
        var haystack = option.text.toLowerCase();

        var match;
        if (matchType === Const.COMBOBOX_MULTIWORD) {
            // Multiword filter, matches any choice that contains all of the words in the query
            //
            // Assumption is both query and choice will not be very long. Runtime is O(nm)
            // where n is number of words in the query, and m is number of words in the choice
            var wordsInQuery = query.split(' ');
            var wordsInChoice = haystack.split(' ');

            match = _.all(wordsInQuery, function (word) {
                return _.include(wordsInChoice, word);
            });
        } else if (matchType === Const.COMBOBOX_FUZZY) {
            // Fuzzy filter, matches if query is "close" to answer
            match = (
                (window.Levenshtein.get(haystack, query) <= 2 && query.length > 3) ||
                haystack === query
            );
        }

        // If we've already matched, return true
        if (match) {
            return true;
        }

        // Standard filter, matches only start of word
        return haystack.startsWith(query);
    };

    ComboboxEntry.prototype = Object.create(DropdownEntry.prototype);
    ComboboxEntry.prototype.constructor = DropdownEntry;
    ComboboxEntry.prototype.onPreProcess = function (newValue) {
        var value;
        if (newValue === Const.NO_ANSWER || newValue === '') {
            this.answer(Const.NO_ANSWER);
            this.question.error(null);
            return;
        }

        value = _.find(this.options(), function (d) {
            return d.id === newValue;
        });
        if (value) {
            this.answer(value.id);
            this.question.error(null);
        } else {
            this.question.error(gettext('Not a valid choice'));
        }
    };
    ComboboxEntry.prototype.receiveMessage = function (message, field) {
        // Iterates through options and selects an option that matches message[field].
        // Registers a no answer if message[field] is not in options.
        // Also accepts fields in format `field1||field2||...||fieldn` it will find the
        // first message[field] that matches an option.
        var self = this;
        var options = self.options();
        var fieldsByPriority = field.split("||");
        for (var i = 0; i < fieldsByPriority.length; i++) {
            var fieldByPriority = fieldsByPriority[i];
            for (var j = 0; j < options.length; j++) {
                var option = options[j];
                if (option.text === message[fieldByPriority]) {
                    self.rawAnswer(option.id);
                    return;
                }
            }
        }
        // no options match message[field]
        self.rawAnswer(Const.NO_ANSWER);
    };

    $.datetimepicker.setDateFormatter({
        parseDate: function (date, format) {
            var d = moment(date, format);
            return d.isValid() ? d.toDate() : false;
        },
        formatDate: function (date, format) {
            return moment(date).format(format);
        },
    });
    /**
     * Base class for DateEntry, TimeEntry, and DateTimeEntry. Shares the same
     * date picker between the three types of Entry.
     */
    function DateTimeEntryBase(question, options) {
        var self = this,
            thisYear = new Date().getFullYear(),
            minDate,
            maxDate,
            yearEnd,
            yearStart,
            displayOpts = _getDisplayOptions(question),
            isPhoneMode = ko.utils.unwrapObservable(displayOpts.phoneMode);

        EntrySingleAnswer.call(self, question, options);

        // Set year ranges
        yearEnd = thisYear + 10;
        yearStart = thisYear - 100;
        // Set max date to 10 years in the future
        maxDate = moment(yearEnd, 'YYYY').toDate();
        // Set min date to 100 years in the past
        minDate = moment(yearStart, 'YYYY').toDate();

        self.afterRender = function () {
            self.$picker = $('#' + self.entryId);
            var datepickerOpts = {
                timepicker: self.timepicker,
                datepicker: self.datepicker,
                format: self.clientFormat,
                formatTime: self.clientTimeFormat,
                formatDate: self.clientDateFormat,
                value: self.answer() ? self.convertServerToClientFormat(self.answer()) : self.answer(),
                maxDate: maxDate,
                minDate: minDate,
                yearEnd: yearEnd,
                yearStart: yearStart,
                scrollInput: false,
                onChangeDateTime: function (newDate) {
                    if (!newDate) {
                        self.answer(Const.NO_ANSWER);
                        return;
                    }
                    self.answer(moment(newDate).format(self.serverFormat));
                },
                onGenerate: function () {
                    var $dt = $(this);
                    if ($dt.find('.xdsoft_mounthpicker .xdsoft_prev .fa').length < 1) {
                        $dt.find('.xdsoft_mounthpicker .xdsoft_prev').append($('<i class="fa fa-chevron-left" />'));
                    }
                    if ($dt.find('.xdsoft_mounthpicker .xdsoft_next .fa').length < 1) {
                        $dt.find('.xdsoft_mounthpicker .xdsoft_next').append($('<i class="fa fa-chevron-right" />'));
                    }

                    if ($dt.find('.xdsoft_timepicker .xdsoft_prev .fa').length < 1) {
                        $dt.find('.xdsoft_timepicker .xdsoft_prev').append($('<i class="fa fa-chevron-up" />'));
                    }
                    if ($dt.find('.xdsoft_timepicker .xdsoft_next .fa').length < 1) {
                        $dt.find('.xdsoft_timepicker .xdsoft_next').append($('<i class="fa fa-chevron-down" />'));
                    }

                    if ($dt.find('.xdsoft_today_button .fa').length < 1) {
                        $dt.find('.xdsoft_today_button').append($('<i class="fa fa-home" />'));
                    }

                    $dt.find('.xdsoft_label i').addClass('fa fa-caret-down');

                    if (isPhoneMode && !self.datepicker && self.timepicker) {
                        $dt.find('.xdsoft_time_box').addClass('time-box-full');
                    }

                    if (isPhoneMode && self.timepicker && self.datepicker) {
                        $dt.find('.xdsoft_save_selected')
                            .show().text(gettext('Save'))
                            .addClass('btn btn-primary')
                            .removeClass('blue-gradient-button');
                        $dt.find('.xdsoft_save_selected').appendTo($dt);
                    }
                },
            };
            self.$picker.datetimepicker(datepickerOpts);
        };
    }
    DateTimeEntryBase.prototype = Object.create(EntrySingleAnswer.prototype);
    DateTimeEntryBase.prototype.constructor = EntrySingleAnswer;
    DateTimeEntryBase.prototype.convertServerToClientFormat = function (date) {
        return moment(date, this.serverFormat).format(this.clientFormat);
    };

    // Format for time or date or datetime for the browser. Defaults to ISO.
    // Formatting string should be in datetimepicker format: http://xdsoft.net/jqplugins/datetimepicker/
    DateTimeEntryBase.prototype.clientFormat = undefined;
    DateTimeEntryBase.prototype.clientTimeFormat = undefined;
    DateTimeEntryBase.prototype.clientDateFormat = undefined;

    // Format for time or date or datetime for the server. Defaults to ISO.
    // Formatting string should be in momentjs format: http://momentjs.com/docs/#/parsing/string-format/
    DateTimeEntryBase.prototype.serverFormat = undefined;

    function DateEntry(question, options) {
        this.templateType = 'date';
        this.timepicker = false;
        this.datepicker = true;
        DateTimeEntryBase.call(this, question, options);
    }
    DateEntry.prototype = Object.create(DateTimeEntryBase.prototype);
    DateEntry.prototype.constructor = DateTimeEntryBase;
    // This is format equates to 12/31/2016 and is used by the datetimepicker
    DateEntry.prototype.clientFormat = 'MM/DD/YYYY';
    DateEntry.prototype.clientDateFormat = 'MM/DD/YYYY';
    DateEntry.prototype.serverFormat = 'YYYY-MM-DD';

    function TimeEntry(question, options) {
        this.templateType = 'time';
        this.timepicker = true;
        this.datepicker = false;
        DateTimeEntryBase.call(this, question, options);
    }
    TimeEntry.prototype = Object.create(DateTimeEntryBase.prototype);
    TimeEntry.prototype.constructor = DateTimeEntryBase;

    TimeEntry.prototype.clientTimeFormat = 'HH:mm';
    TimeEntry.prototype.clientFormat = 'HH:mm';
    TimeEntry.prototype.serverFormat = 'HH:mm';

    function EthiopianDateEntry(question, options) {
        var self = this,
            ethiopianLanguageMap = {
                am: 'amh',
                amh: 'amh',
                ti: 'tir',
                tir: 'tir',
                or: 'orm',
                orm: 'orm',
            },
            calendarLanguage = ethiopianLanguageMap[initialPageData.get('language')] ? ethiopianLanguageMap[initialPageData.get('language')] : 'en';

        self.templateType = 'ethiopian-date';

        EntrySingleAnswer.call(self, question, options);

        self._calendarInstance = $.calendars.instance('ethiopian', calendarLanguage);
        if (calendarLanguage === 'en') {
            $.calendarsPicker.setDefaults($.calendarsPicker.regionalOptions['']);
        } else {
            $.calendarsPicker.setDefaults($.calendarsPicker.regionalOptions[calendarLanguage]);
        }

        self._formatDateForAnswer = function (newDate) {
            return moment(newDate).format('YYYY-MM-DD');
        };

        self.afterRender = function () {
            self.$picker = $('#' + self.entryId);
            self.$picker.calendarsPicker({
                calendar: self._calendarInstance,
                showAnim: '',
                onSelect: function (dates) {
                    // transform date to gregorian to store as the answer
                    if (dates.length) {
                        self.answer(self._formatDateForAnswer(dates[0].toJSDate()));
                    } else {
                        self.answer(Const.NO_ANSWER);
                    }
                },
            });

            self.$picker.blur(function (change) {
                // calendarsPicker doesn't pick up changes if you don't actively select them in the widget
                var changedPicker = $(change.target)[0],
                    newDate = self._calendarInstance.parseDate(
                        self._calendarInstance.local.dateFormat,
                        changedPicker.value
                    );

                if (newDate && (self.answer() !== self._formatDateForAnswer(newDate.toJSDate()))) {
                    self.$picker.calendarsPicker('setDate', changedPicker.value);
                }
            });

            if (self.answer()) {
                // convert any default values to ethiopian and set it
                var ethiopianDate = self._calendarInstance.fromJSDate(moment(self.answer()).toDate());
                self.$picker.calendarsPicker('setDate', ethiopianDate);
            }
        };

    }
    EthiopianDateEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    EthiopianDateEntry.prototype.constructor = EntrySingleAnswer;

    function GeoPointEntry(question, options) {
        var self = this;
        EntryArrayAnswer.call(self, question, options);
        self.templateType = 'geo';
        self.map = null;
        self.control_width = Const.CONTROL_WIDTH;

        self.DEFAULT = {
            lat: 30,
            lon: 0,
            zoom: 1,
            anszoom: 6,
        };

        self.onClear = function () {
            self.rawAnswer([]);
        };

        self.loadMap = function () {
            var token = initialPageData.get("mapbox_access_token");
            if (token) {
                self.map = L.map(self.entryId).setView([self.DEFAULT.lat, self.DEFAULT.lon], self.DEFAULT.zoom);
                L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token='
                            + token, {
                    id: 'mapbox/streets-v11',
                    attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                                 ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
                    tileSize: 512,
                    zoomOffset: -1,
                }).addTo(self.map);
                self.map.on('move', self.updateCenter);

                self.centerMarker = L.marker(self.map.getCenter()).addTo(self.map);

                L.mapbox.accessToken = token;
                self.geocoder = L.mapbox.geocoder('mapbox.places');
            } else {
                question.error(gettext('Map layer not configured.'));
            }

        };

        self.afterRender = function () {
            if (typeof L === 'undefined') {
                question.error(gettext('Could not load map. Please try again later.'));
            } else {
                self.loadMap();
            }
        };

        self.updateCenter = function () {
            var center = self.map.getCenter();
            self.centerMarker.setLatLng(center);
            self.rawAnswer([center.lat, center.lng]);
        };

        self.formatLat = function () {
            return self.formatCoordinate(self.rawAnswer()[0] || null, ['N', 'S']);
        };
        self.formatLon = function () {
            return self.formatCoordinate(self.rawAnswer()[1] || null, ['E', 'W']);
        };
        self.formatCoordinate = function (coordinate, cardinalities) {
            var cardinality = coordinate >= 0 ? cardinalities[0] : cardinalities[1];
            if (coordinate !== null) {
                return cardinality + intpad(intpad(Math.abs(coordinate).toFixed(5), 8));
            }
            return '??.?????';
        };

        self.search = function (form) {
            var query = $(form).find('.query').val();
            self.geocoder.query(query, function (err, data) {
                if (err === null) {
                    if (data.lbounds !== null) {
                        self.map.fitBounds(data.lbounds);
                    } else if (data.latlng !== null) {
                        self.map.setView([data.latlng[0], data.latlng[1]], self.DEFAULT.zoom);
                    }
                }
            });
        };
    }
    GeoPointEntry.prototype = Object.create(EntryArrayAnswer.prototype);
    GeoPointEntry.prototype.constructor = EntryArrayAnswer;


    /**
     * Gets the entry based on the datatype of the Question
     * @param {Object} question - A Question object
     */
    function getEntry(question) {
        var hasGeocoderPrivs = initialPageData.get("has_geocoder_privs");
        var entry = null;
        var options = {};
        var isMinimal = false;
        var isCombobox = false;
        var isLabel = false;
        var hideLabel = false;
        var style;

        if (question.style) {
            style = ko.utils.unwrapObservable(question.style.raw);
        }

        var displayOptions = _getDisplayOptions(question);
        var isPhoneMode = ko.utils.unwrapObservable(displayOptions.phoneMode);
        var receiveStyle = (question.stylesContains(/receive-*/)) ? question.stylesContaining(/receive-*/)[0] : null;

        switch (question.datatype()) {
            case Const.STRING:
                // Barcode uses text box for CloudCare so it's possible to still enter a barcode field
            case Const.BARCODE:     // eslint-disable-line no-fallthrough
                // If it's a receiver, it cannot autoupdate because updates will come quickly which messes with the
                // autoupdate rate limiting.
                if (receiveStyle) {
                    options.receiveStyle = receiveStyle;
                } else {
                    options.enableAutoUpdate = isPhoneMode;
                }
                if (question.stylesContains(Const.ADDRESS)) {
                    if (hasGeocoderPrivs) {
                        entry = new AddressEntry(question, {
                            broadcastStyles: question.stylesContaining(/broadcast-*/),
                        });
                    } else {
                        window.console.warn('No active entry for: ' + question.datatype());
                        entry = new UnsupportedEntry(question, options);
                    }
                } else if (question.stylesContains(Const.NUMERIC)) {
                    entry = new PhoneEntry(question, options);
                } else {
                    entry = new FreeTextEntry(question, options);
                }
                break;
            case Const.INT:
                entry = new IntEntry(question, {
                    enableAutoUpdate: isPhoneMode,
                });
                break;
            case Const.LONGINT:
                entry = new IntEntry(question, {
                    lengthLimit: Const.LONGINT_LENGTH_LIMIT,
                    valueLimit: Const.LONGINT_VALUE_LIMIT,
                    enableAutoUpdate: isPhoneMode,
                });
                break;
            case Const.FLOAT:
                entry = new FloatEntry(question, {
                    enableAutoUpdate: isPhoneMode,
                });
                break;
            case Const.SELECT:
                isMinimal = style === Const.MINIMAL;
                if (style) {
                    isCombobox = question.stylesContains(Const.COMBOBOX);
                }
                if (style) {
                    isLabel = style === Const.LABEL || style === Const.LIST_NOLABEL;
                    hideLabel = style === Const.LIST_NOLABEL;
                }

                if (isMinimal) {
                    entry = new DropdownEntry(question, {});
                } else if (isCombobox) {
                    entry = new ComboboxEntry(question, {
                        /*
                         * The appearance attribute is either:
                         *
                         * combobox
                         * combobox multiword
                         * combobox fuzzy
                         *
                         * The second word designates the matching type
                         */
                        matchType: question.style.raw().split(' ')[1],
                        receiveStyle: receiveStyle,
                    });
                } else if (isLabel) {
                    entry = new ChoiceLabelEntry(question, {
                        hideLabel: hideLabel,
                    });
                } else {
                    entry = new SingleSelectEntry(question, {
                        receiveStyle: receiveStyle,
                    });
                }
                break;
            case Const.MULTI_SELECT:
                isMinimal = style === Const.MINIMAL;
                if (isMinimal) {
                    entry = new MultiDropdownEntry(question, {});
                } else {
                    entry = new MultiSelectEntry(question, {});
                }
                break;
            case Const.DATE:
                if (style === Const.ETHIOPIAN) {
                    entry = new EthiopianDateEntry(question, {});
                } else {
                    entry = new DateEntry(question, {});
                }
                break;
            case Const.TIME:
                entry = new TimeEntry(question, {});
                break;
            case Const.GEO:
                entry = new GeoPointEntry(question, {});
                break;
            case Const.INFO:
                entry = new InfoEntry(question, {});
                break;
            default:
                window.console.warn('No active entry for: ' + question.datatype());
                entry = new UnsupportedEntry(question, options);
        }
        return entry;
    }

    function intpad(x, n) {
        var s = x + '';
        while (s.length < n) {
            s = '0' + s;
        }
        return s;
    }

    /**
     * Utility that gets the display options from a parent form of a question.
     * */
    function _getDisplayOptions(question) {
        var maxIter = 10; // protect against a potential infinite loop
        var form = question.parent;

        if (form === undefined) {
            return {};
        }

        // logic in case the question is in a group or repeat or nested group, etc.
        while (form.displayOptions === undefined && maxIter > 0) {
            maxIter--;
            form = parent.parent;
        }

        return form.displayOptions || {};
    }

    /**
     * Utility to render question as select2
     * additionalOptions is passed as object to select2 constructor
     */
    function select2ify(entry, additionalOptions) {
        var $input = $('#' + entry.entryId);
        $input.select2(_.extend({
            allowClear: true,
            placeholder: entry.placeholderText,
            escapeMarkup: function (m) { return DOMPurify.sanitize(m); },
        }, additionalOptions));

    }

    /**
     * Function to handle answer changes for entries using selct2
     */
    function select2AnswerChange(parentClass) {
        return function(newValue) {
            var self = this;
            parentClass.prototype.onAnswerChange.call(self, newValue);
            _.delay(function () {
                $("#" + self.entryId).trigger("change.select2");
            });
        };
    }

    return {
        getEntry: getEntry,
        AddressEntry: AddressEntry,
        ComboboxEntry: ComboboxEntry,
        DateEntry: DateEntry,
        DropdownEntry: DropdownEntry,
        EthiopianDateEntry: EthiopianDateEntry,
        FloatEntry: FloatEntry,
        FreeTextEntry: FreeTextEntry,
        InfoEntry: InfoEntry,
        IntEntry: IntEntry,
        MultiSelectEntry: MultiSelectEntry,
        MultiDropdownEntry: MultiDropdownEntry,
        PhoneEntry: PhoneEntry,
        SingleSelectEntry: SingleSelectEntry,
        TimeEntry: TimeEntry,
    };
});
