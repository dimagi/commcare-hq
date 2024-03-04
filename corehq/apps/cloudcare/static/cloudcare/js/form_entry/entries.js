/* globals moment, SignaturePad, DOMPurify */
hqDefine("cloudcare/js/form_entry/entries", function () {
    var kissmetrics = hqImport("analytix/js/kissmetrix"),
        cloudcareUtils = hqImport("cloudcare/js/utils"),
        constants = hqImport("cloudcare/js/form_entry/const"),
        formEntryUtils = hqImport("cloudcare/js/form_entry/utils"),
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        toggles = hqImport("hqwebapp/js/toggles");

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
        self.xformAction = constants.ANSWER;
        self.xformParams = function () { return {}; };
        self.placeholderText = '';
        // Returns true if the rawAnswer is valid, false otherwise
        self.isValid = function (rawAnswer) {
            return self.getErrorMessage(rawAnswer) === null;
        };

        // Returns an error message given the answer. null if no error
        self.getErrorMessage = function () {
            return null;
        };

        self.clear = function () {
            self.answer(constants.NO_ANSWER);
        };
        self.useHintAsPlaceHolder = ko.computed(function () {
            return ko.utils.unwrapObservable(question.hint) && question.stylesContains(constants.HINT_AS_PLACEHOLDER);
        });
        self.setPlaceHolder(self.useHintAsPlaceHolder());
        self.afterRender = function () {
            // Override with any logic that comes after rendering the Entry
        };
        if (self.answer) {
            self.answer.subscribe(self.onAnswerChange.bind(self));
        }
    }
    Entry.prototype.onAnswerChange = function () {};

    // Allows multiple input entries on the same row for Combined Multiple Choice and Combined
    // Checkbox questions in a Question List Group.
    Entry.prototype.getColStyle = function (numChoices) {
        // Account for number of choices plus column for clear button
        var colWidth = parseInt(12 / (numChoices + 1)) || 1;
        return 'col-xs-' + colWidth;
    };

    // This should set the answer value if the answer is valid. If the raw answer is valid, this
    // function performs any sort of processing that needs to be done before setting the answer.
    Entry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            this.answer(newValue);
        }
        this.question.error(this.getErrorMessage(newValue));
    };

    Entry.prototype.setPlaceHolder = function (hasPlaceHolder) {
        const self = this;
        if (hasPlaceHolder) {
            self.placeholderText = ko.utils.unwrapObservable(self.question.hint);
        }
    };

    /**
     * Serves as the base for all entries that take an array answer.
     */
    function EntryArrayAnswer(question) {
        var self = this;
        Entry.call(self, question);
        self.rawAnswer = ko.observableArray(_.clone(question.answer()));

        self.rawAnswer.subscribe(self.onPreProcess.bind(self));
        self.previousAnswer = self.answer();
    }
    EntryArrayAnswer.prototype = Object.create(Entry.prototype);
    EntryArrayAnswer.prototype.constructor = Entry;
    EntryArrayAnswer.prototype.onAnswerChange = function () {
        if (formEntryUtils.answersEqual(this.answer(), this.previousAnswer)) {
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
                processed = constants.NO_ANSWER;
            }

            if (!formEntryUtils.answersEqual(processed, this.answer())) {
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
                return constants.NO_ANSWER;
            }
            return answer;
        };

        Entry.call(self, question);
        self.valueUpdate = undefined;
        self.rawAnswer = ko.observable(getRawAnswer(question.answer()));

        self.rawAnswer.subscribe(self.onPreProcess.bind(self));

        if (options.enableAutoUpdate) {
            self.valueUpdate = 'keyup';
            self.answer.extend({
                rateLimit: {
                    timeout: constants.KO_ENTRY_TIMEOUT,
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
                question.broadcastPubSub.subscribe(function (message) {
                    if (message === constants.NO_ANSWER) {
                        self.rawAnswer(constants.NO_ANSWER);
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
            self.rawAnswer(constants.NO_ANSWER);
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
        var isPassword = ko.utils.unwrapObservable(question.control) === constants.CONTROL_SECRET;
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

        self.enableReceiver(question, options);
    }
    FreeTextEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    FreeTextEntry.prototype.constructor = EntrySingleAnswer;
    FreeTextEntry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            this.answer(newValue === '' ? constants.NO_ANSWER : newValue);
        }
        this.question.error(this.getErrorMessage(newValue));
    };


    /**
     * The entry that represents an address entry.
     * Takes in a `broadcastStyles` list of strings in format `broadcast-<topic>` to broadcast
     * the address item that is selected. Item contains `full`, `street`, `city`, `us_state`, `us_state_long`,
     * `postcode`, `zipcode`, `district`, `county`, `country`, `country_short`, `region`.
     */
    function AddressEntry(question, options) {
        var self = this;
        FreeTextEntry.call(self, question, options);
        self.templateType = 'address';
        self.broadcastTopics = [];
        self.editing = true;
        let isRequired = self.question.required() ? "Yes" : "No";
        $(function () {
            let entry = $(`#${self.entryId}`);
            entry.on("change", function () {
                kissmetrics.track.event("Accessibility Tracking - Geocoder Question Interaction");
            });
        });
        kissmetrics.track.event("Accessibility Tracking - Geocoder Question Seen", {
            "Required": isRequired,
        });
        // Callback for the geocoder when an address item is selected. We intercept here and broadcast to
        // subscribers.
        self.geocoderItemCallback = function (item) {
            self.rawAnswer(item.place_name);
            self.editing = false;
            var broadcastObj = formEntryUtils.getBroadcastObject(item);
            self.broadcastTopics.forEach(function (broadcastTopic) {
                question.broadcastPubSub.notifySubscribers(broadcastObj, broadcastTopic);
            });
            if (_.isEmpty(broadcastObj)) {
                question.answer(constants.NO_ANSWER);
            } else {
                question.answer(JSON.stringify(broadcastObj));
            }
            // The default full address returned to the search bar
            return item.place_name;
        };

        // geocoder function called when user presses 'x', broadcast a no answer to subscribers.
        self.geocoderOnClearCallback = function () {
            self.rawAnswer(constants.NO_ANSWER);
            self.question.error(null);
            self.editing = true;
            self.broadcastTopics.forEach(function (broadcastTopic) {
                question.broadcastPubSub.notifySubscribers(constants.NO_ANSWER, broadcastTopic);
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

            formEntryUtils.renderMapboxInput({
                divId: self.entryId,
                itemCallback: self.geocoderItemCallback,
                clearCallBack: self.geocoderOnClearCallback,
                inputOnKeyDown: self._inputOnKeyDown,
            });
        };

        self._inputOnKeyDown = function (event) {
            // On key down, switch to editing mode so we unregister an answer.
            if (!self.editing && self.rawAnswer() !== event.target.value) {
                self.rawAnswer(constants.NO_ANSWER);
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
        self.lengthLimit = options.lengthLimit || constants.INT_LENGTH_LIMIT;
        var valueLimit = options.valueLimit || constants.INT_VALUE_LIMIT;

        self.getErrorMessage = function (rawAnswer) {
            if (isNaN(+rawAnswer) || +rawAnswer !== Math.floor(+rawAnswer)) {
                return gettext("Not a valid whole number");
            }
            if (+rawAnswer > valueLimit) {
                return gettext("Number is too large");
            }
            return null;
        };

        self.enableReceiver(question, options);
    }
    IntEntry.prototype = Object.create(FreeTextEntry.prototype);
    IntEntry.prototype.constructor = FreeTextEntry;

    IntEntry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            if (newValue === '') {
                this.answer(constants.NO_ANSWER);
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
        this.lengthLimit = options.lengthLimit || constants.FLOAT_LENGTH_LIMIT;
        var valueLimit = options.valueLimit || constants.FLOAT_VALUE_LIMIT;

        this.getErrorMessage = function (rawAnswer) {
            if (isNaN(+rawAnswer)) {
                return gettext("Not a valid number");
            }
            if (+rawAnswer > valueLimit) {
                return gettext("Number is too large");
            }
            return null;
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
        self.hideLabel = options.hideLabel;

        self.rawAnswer = ko.pureComputed({
            read: () => {
                let answer = this.answer();
                if (answer === constants.NO_ANSWER) {
                    return [];
                }

                let choices = this.choices();
                return answer.map(index => choices[index - 1]);
            },
            write: (value) => {
                let choices = this.choices.peek();
                // answer is based on a 1 indexed index of the choices
                let answer = _.filter(value.map((val) => _.indexOf(choices, val) + 1), (v) => v > 0);
                self.onPreProcess.call(this, answer);
            },
        });

        self.colStyleIfHideLabel = ko.computed(function () {
            return self.hideLabel ? self.getColStyle(self.choices().length) : null;
        });

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
        if (!self.placeholderText.length) {
            self.placeholderText = gettext('Please choose an item');
        }
        self.afterRender = function () {
            select2ify(self, {}, true);
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

        self.rawAnswer = ko.pureComputed({
            read: () => {
                let answer = this.answer();
                if (!answer) {
                    return constants.NO_ANSWER;
                }

                let choices = this.choices();
                return choices[answer - 1];
            },
            write: (value) => {
                let choices = this.choices.peek();
                let answer = _.indexOf(choices, value);
                // answer is based on a 1 indexed index of the choices
                this.answer(answer === -1 ? constants.NO_ANSWER : answer + 1);
            },
        });

        self.onClear = function () {
            self.rawAnswer(constants.NO_ANSWER);
        };

        self.enableReceiver(question, options);
    }
    SingleSelectEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    SingleSelectEntry.prototype.constructor = EntrySingleAnswer;
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
        self.rawAnswer(constants.NO_ANSWER);
    };

    /**
     * Represents a single button that cycles through choices
     */
    function ButtonSelectEntry(question, options) {
        var self = this;
        SingleSelectEntry.call(this, question, options);
        self.templateType = 'button';

        self.buttonLabel = function () {
            const choices = self.choices();
            const answer = self.answer() || 0;
            return answer < choices.length ? choices[answer] : choices[0];
        };

        self.onClick = function () {
            const answer = self.answer();
            if (answer && answer < self.choices().length) {
                self.answer(answer + 1);
            } else {
                self.answer(1);
            }
        };
    }
    ButtonSelectEntry.prototype = Object.create(SingleSelectEntry.prototype);
    ButtonSelectEntry.prototype.constructor = SingleSelectEntry;

    /**
     * This is used for the labels and inputs in a Combined Multiple Choice question in a Question
     * List Group. It is also used for labels in a Combined Checkbox question.
     */
    function ChoiceLabelEntry(question, options) {
        var self = this;
        EntrySingleAnswer.call(this, question, options);
        self.choices = question.choices;
        self.templateType = 'choice-label';

        self.hideLabel = options.hideLabel;

        self.colStyle = ko.computed(function () {
            return self.getColStyle(self.choices().length);
        });

        self.onClear = function () {
            self.rawAnswer(constants.NO_ANSWER);
        };
        self.isValid = function () {
            return true;
        };
    }
    ChoiceLabelEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    ChoiceLabelEntry.prototype.constructor = EntrySingleAnswer;
    ChoiceLabelEntry.prototype.onPreProcess = function (newValue) {
        if (this.isValid(newValue)) {
            if (newValue === constants.NO_ANSWER) {
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
        if (!self.placeholderText.length) {
            self.placeholderText = gettext('Please choose an item');
        }
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
            select2ify(self, self.additionalSelect2Options(), false);
        };
    }
    DropdownEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    DropdownEntry.prototype.constructor = EntrySingleAnswer;
    DropdownEntry.prototype.onAnswerChange = select2AnswerChange(EntrySingleAnswer);
    DropdownEntry.prototype.onPreProcess = function (newValue) {
        // When newValue is undefined it means we've unset the select question.
        if (newValue === constants.NO_ANSWER || newValue === undefined) {
            this.answer(constants.NO_ANSWER);
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

        var match,
            wordsInQuery = query.split(/\s+/),
            wordsInChoice = haystack.split(/\s+/);
        if (matchType === constants.COMBOBOX_MULTIWORD) {
            // Multiword filter, matches any choice that contains all of the words in the query
            //
            // Assumption is both query and choice will not be very long. Runtime is O(nm)
            // where n is number of words in the query, and m is number of words in the choice

            match = _.all(wordsInQuery, function (word) {
                return _.include(wordsInChoice, word);
            });
        } else if (matchType === constants.COMBOBOX_FUZZY) {
            var isFuzzyMatch = function (haystack, query, distanceThreshold) {
                return (
                    haystack === query ||
                    (query.length > 3 && window.Levenshtein.get(haystack, query) <= distanceThreshold)
                );
            };

            // First handle prefixes, which will fail fuzzy match if they're too short
            var distanceThreshold = 2;
            if (haystack.length > query.length + distanceThreshold) {
                haystack = haystack.substring(0, query.length + distanceThreshold);
            }

            // Fuzzy filter, matches if query is "close" to answer
            match = isFuzzyMatch(haystack, query, distanceThreshold);

            // For multiword strings, return true if any word in the query fuzzy matches any word in the target
            if (!match) {
                if (wordsInChoice.length > 1 || wordsInQuery.length > 1) {
                    _.each(wordsInChoice, function (choiceWord) {
                        _.each(wordsInQuery, function (queryWord) {
                            match = match || isFuzzyMatch(choiceWord, queryWord, distanceThreshold);
                        });
                    });
                }
            }
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
        if (newValue === constants.NO_ANSWER || newValue === '') {
            this.answer(constants.NO_ANSWER);
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
        self.rawAnswer(constants.NO_ANSWER);
    };

    /**
     * Base class for DateEntry, TimeEntry, and DateTimeEntry. Shares the same
     * date picker between the three types of Entry.
     */
    function DateTimeEntryBase(question, options) {
        var self = this;

        EntrySingleAnswer.call(self, question, options);

        self.afterRender = function () {
            self.$picker = $('#' + self.entryId);

            var answer = self.answer() ? self.convertServerToClientFormat(self.answer()) : constants.NO_ANSWER;
            self.initWidget(self.$picker, answer);

            self.$picker.on("dp.change", function (e) {
                if (!e.date) {
                    self.answer(constants.NO_ANSWER);
                    return;
                }
                self.answer(moment(e.date.toDate()).format(self.serverFormat));
            });
        };
    }
    DateTimeEntryBase.prototype = Object.create(EntrySingleAnswer.prototype);
    DateTimeEntryBase.prototype.constructor = EntrySingleAnswer;
    DateTimeEntryBase.prototype.initWidget = undefined;  // overridden in subclasses
    DateTimeEntryBase.prototype.convertServerToClientFormat = function (date) {
        return moment(date, this.serverFormat).format(this.clientFormat);
    };

    // Format for time or date or datetime for the browser. Defaults to ISO.
    // Formatting string should be in moment format: https://momentjs.com/docs/#/displaying/format/
    DateTimeEntryBase.prototype.clientFormat = undefined;

    // Format for time or date or datetime for the server. Defaults to ISO.
    // Formatting string should be in moment format: https://momentjs.com/docs/#/displaying/format/
    DateTimeEntryBase.prototype.serverFormat = undefined;

    function DateEntry(question, options) {
        this.templateType = 'date';
        DateTimeEntryBase.call(this, question, options);
    }
    DateEntry.prototype = Object.create(DateTimeEntryBase.prototype);
    DateEntry.prototype.constructor = DateTimeEntryBase;
    // This is format equates to 12/31/2016 and is used by the datetimepicker
    DateEntry.prototype.clientFormat = 'MM/DD/YYYY';
    DateEntry.prototype.serverFormat = 'YYYY-MM-DD';
    DateEntry.prototype.initWidget = function ($element, answer) {
        cloudcareUtils.initDatePicker($element, answer);
    };

    function TimeEntry(question, options) {
        this.templateType = 'time';
        if (question.style) {
            if (question.stylesContains(constants.TIME_12_HOUR)) {
                this.clientFormat = 'h:mm a';
            }
        }
        DateTimeEntryBase.call(this, question, options);
    }
    TimeEntry.prototype = Object.create(DateTimeEntryBase.prototype);
    TimeEntry.prototype.constructor = DateTimeEntryBase;

    TimeEntry.prototype.clientFormat = 'HH:mm';
    TimeEntry.prototype.serverFormat = 'HH:mm';
    TimeEntry.prototype.initWidget = function ($element, answer) {
        cloudcareUtils.initTimePicker($element, answer, this.clientFormat);
    };

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
                        self.answer(constants.NO_ANSWER);
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

    /**
     * Base class for entry types that involve uploading a file: multimedia and signatures.
     */
    function FileEntry(question, options) {
        var self = this;
        EntrySingleAnswer.call(this, question, options);
        self.templateType = 'file';
        self.xformAction = constants.ANSWER_MEDIA;
        self.xformParams = function () {
            return { file: self.file() };
        };
        self.file = ko.observable();
        self.extensionsMap = initialPageData.get("valid_multimedia_extensions_map");
        // Tracks whether file entry has already been cleared, preventing an additional failing request to Formplayer
        self.cleared = false;
    }
    FileEntry.prototype = Object.create(EntrySingleAnswer.prototype);
    FileEntry.prototype.constructor = EntrySingleAnswer;
    FileEntry.prototype.onPreProcess = function (newValue) {
        var self = this;
        if (newValue !== constants.NO_ANSWER && newValue !== "") {
            // Input has changed and validation will be checked
            if (newValue !== self.answer()) {
                self.question.formplayerProcessed = false;
                self.cleared = false;
            }
            self.answer(newValue.replace(constants.FILE_PREFIX, ""));
        } else {
            self.onClear();
        }
    };
    FileEntry.prototype.onAnswerChange = function (newValue) {
        var self = this;
        // file has already been validated and assigned a unique id. another request should not be sent to formplayer
        if (self.question.formplayerProcessed) {
            return;
        }
        if (newValue !== constants.NO_ANSWER && newValue !== "") {
            var $input = $('#' + self.entryId);
            self.file($input[0].files[0]);
            let badExtension = false;
            let badMime = true;
            const ext = newValue.slice(newValue.lastIndexOf(".") + 1);
            const acceptedExts = self.extensionsMap[self.accept];
            badExtension = !acceptedExts.includes(ext.toLowerCase());

            for (const acc of self.accept.split(",")) {
                if (self.file().type.match(acc)) {
                    badMime = false;
                    break;
                }
            }
            // corresponds to validateFile check in Formplayer
            // any changes made here should also be made in Formplayer
            if (badExtension || badMime) {
                self.question.error(gettext("Invalid file type chosen. Please select a valid multimedia file."));
                return;
            }
            // corresponds to MAX_BYTES_PER_ATTACHMENT var in Formplayer and limits file uploads to 4MB
            // any changes made here should also be made in Formplayer
            if (self.file().size > 4000000) {
                self.question.error(gettext("The file you selected exceeds the size limit of 4MB. Please select a file that is smaller than 4MB."));
                return;
            }
            self.question.error(null);
            self.question.onchange();
        }
    };
    FileEntry.prototype.onClear = function () {
        var self = this;
        if (self.cleared) {
            return;
        }
        self.cleared = true;
        self.file(null);
        self.rawAnswer(constants.NO_ANSWER);
        self.xformAction = constants.CLEAR_ANSWER;
        self.question.onClear();
    };

    /**
     * Represents an image upload.
     */
    function ImageEntry(question, options) {
        var self = this;
        FileEntry.call(this, question, options);
        self.accept = "image/*,.pdf";
    }
    ImageEntry.prototype = Object.create(FileEntry.prototype);
    ImageEntry.prototype.constructor = FileEntry;

    /**
     * Represents an audio upload.
     */
    function AudioEntry(question, options) {
        var self = this;
        FileEntry.call(this, question, options);
        self.accept = "audio/*";
    }
    AudioEntry.prototype = Object.create(FileEntry.prototype);
    AudioEntry.prototype.constructor = FileEntry;

    /**
     * Represents a video upload.
     */
    function VideoEntry(question, options) {
        var self = this;
        FileEntry.call(this, question, options);
        self.accept = "video/*";
    }
    VideoEntry.prototype = Object.create(FileEntry.prototype);
    VideoEntry.prototype.constructor = FileEntry;

    /**
     * Represents a signature capture, which requires the user to draw a signature.
     */
    function SignatureEntry(question, options) {
        var self = this;
        FileEntry.call(this, question, options);
        self.templateType = 'signature';
        self.accept = 'image/*,.pdf';

        self.afterRender = function () {
            self.$input = $('#' + self.entryId);
            self.$canvas = $('#' + self.entryId + '-canvas');
            self.$wrapper = $('#' + self.entryId + '-wrapper');

            self.signaturePad = new SignaturePad(self.$canvas[0]);
            self.signaturePad.addEventListener('endStroke', () => { self.answerCanvasData(); });

            new ResizeObserver(() => {
                self.resizeCanvas();
            }).observe(self.$wrapper[0]);

            self.resizeCanvas();
        };

        self.answerCanvasData = function () {
            self.$canvas[0].toBlob(blob => {
                var filename = blob.size + '.png', // simple filename change for validation
                    signatureFile = new File([blob], filename, {type: "image/png"}),
                    list = new DataTransfer();
                list.items.add(signatureFile);
                self.$input[0].files = list.files;
                self.rawAnswer(constants.FILE_PREFIX + filename);
            });
        };

        self.onClear = function () {
            SignatureEntry.prototype.onClear.call(self);
            if (self.signaturePad) {self.signaturePad.clear();}
        };

        self.resizeCanvas = function () {
            var aspectRatio = 4,
                width = self.$wrapper.width() - 2; // otherwise misaligned by 2px
            self.$canvas[0].width = width;
            self.$canvas[0].height = width / aspectRatio;
        };
    }
    SignatureEntry.prototype = Object.create(FileEntry.prototype);
    SignatureEntry.prototype.constructor = FileEntry;

    function GeoPointEntry(question, options) {
        var self = this;
        EntryArrayAnswer.call(self, question, options);
        self.templateType = 'geo';
        self.map = null;
        self.hasMap = () => !!self.map;
        self.control_width = constants.CONTROL_WIDTH;

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
                // if a default answer exists, use that instead
                let lat = self.rawAnswer().length ? self.rawAnswer()[0] : self.DEFAULT.lat;
                let lon = self.rawAnswer().length ? self.rawAnswer()[1] : self.DEFAULT.lon;
                let zoom = self.rawAnswer().length ? self.DEFAULT.anszoom : self.DEFAULT.zoom;

                self.map = L.map(self.entryId, {
                    zoomControl: false,
                }).setView([lat, lon], zoom);
                L.control.zoom({
                    position: 'bottomright',
                }).addTo(self.map);

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
                    if (data.lbounds) {
                        self.map.fitBounds(data.lbounds);
                    } else if (data.latlng) {
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
        var isButton = false;
        var isChoiceLabel = false;
        var hideLabel = false;

        var displayOptions = _getDisplayOptions(question);
        var isPhoneMode = ko.utils.unwrapObservable(displayOptions.phoneMode);
        var receiveStyle = (question.stylesContains(/receive-*/)) ? question.stylesContaining(/receive-*/)[0] : null;

        switch (question.datatype()) {
            case constants.STRING:
                // Barcode uses text box for CloudCare so it's possible to still enter a barcode field
            case constants.BARCODE:     // eslint-disable-line no-fallthrough
                // If it's a receiver, it cannot autoupdate because updates will come quickly which messes with the
                // autoupdate rate limiting.
                if (receiveStyle) {
                    options.receiveStyle = receiveStyle;
                } else {
                    options.enableAutoUpdate = isPhoneMode;
                }
                if (question.stylesContains(constants.ADDRESS)) {
                    if (hasGeocoderPrivs) {
                        entry = new AddressEntry(question, {
                            broadcastStyles: question.stylesContaining(/broadcast-*/),
                        });
                    } else {
                        window.console.warn('No active entry for: ' + question.datatype());
                        entry = new UnsupportedEntry(question, options);
                    }
                } else if (question.stylesContains(constants.NUMERIC)) {
                    entry = new PhoneEntry(question, options);
                } else {
                    entry = new FreeTextEntry(question, options);
                }
                break;
            case constants.INT:
                entry = new IntEntry(question, {
                    enableAutoUpdate: isPhoneMode,
                });
                break;
            case constants.LONGINT:
                entry = new IntEntry(question, {
                    lengthLimit: constants.LONGINT_LENGTH_LIMIT,
                    valueLimit: constants.LONGINT_VALUE_LIMIT,
                    enableAutoUpdate: isPhoneMode,
                });
                break;
            case constants.FLOAT:
                entry = new FloatEntry(question, {
                    enableAutoUpdate: isPhoneMode,
                });
                break;
            case constants.SELECT:
                isMinimal = question.stylesContains(constants.MINIMAL);
                isCombobox = question.stylesContains(constants.COMBOBOX);
                isButton = question.stylesContains(constants.BUTTON_SELECT);
                isChoiceLabel = question.stylesContains(constants.LABEL) || question.stylesContains(constants.LIST_NOLABEL);
                hideLabel = question.stylesContains(constants.LIST_NOLABEL);

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
                } else if (isButton) {
                    entry = new ButtonSelectEntry(question, {});
                } else if (isChoiceLabel) {
                    entry = new ChoiceLabelEntry(question, {
                        hideLabel: hideLabel,
                    });
                    if (!hideLabel) {
                        let isRequired = entry.question.required() ? "Yes" : "No";
                        kissmetrics.track.event("Accessibility Tracking - Tabular Question Seen", {
                            "Required": isRequired,
                        });
                        $(function () {
                            $(".q.form-group").on("change", function () {
                                kissmetrics.track.event("Accessibility Tracking - Tabular Question Interaction");
                            });
                        });

                    }
                } else {
                    entry = new SingleSelectEntry(question, {
                        receiveStyle: receiveStyle,
                    });
                }
                break;
            case constants.MULTI_SELECT:
                isMinimal = question.stylesContains(constants.MINIMAL);
                isChoiceLabel = question.stylesContains(constants.LABEL);
                hideLabel = question.stylesContains(constants.LIST_NOLABEL);

                if (isMinimal) {
                    entry = new MultiDropdownEntry(question, {});
                } else if (isChoiceLabel) {
                    entry = new ChoiceLabelEntry(question, {
                        hideLabel: false,
                    });
                    if (!hideLabel) {
                        let isRequired = entry.question.required() ? "Yes" : "No";
                        kissmetrics.track.event("Accessibility Tracking - Tabular Question Seen", {
                            "Required": isRequired,
                        });
                        $(function () {
                            $(".q.form-group").on("change", function () {
                                kissmetrics.track.event("Accessibility Tracking - Tabular Question Interaction");
                            });
                        });
                    }
                } else if (hideLabel) {
                    entry = new MultiSelectEntry(question, {
                        hideLabel: true,
                    });
                } else {
                    entry = new MultiSelectEntry(question, {});
                }
                break;
            case constants.DATE:
                if (question.stylesContains(constants.ETHIOPIAN)) {
                    entry = new EthiopianDateEntry(question, {});
                } else {
                    entry = new DateEntry(question, {});
                }
                break;
            case constants.TIME:
                entry = new TimeEntry(question, {});
                break;
            case constants.GEO:
                entry = new GeoPointEntry(question, {});
                break;
            case constants.INFO: // it's a label
                entry = new InfoEntry(question, {});
                break;
            case constants.BINARY:
                if (!toggles.toggleEnabled('WEB_APPS_UPLOAD_QUESTIONS')) {
                    // do nothing, fall through to unsupported
                } else {
                    switch (question.control()) {
                        case constants.CONTROL_IMAGE_CHOOSE:
                            if (question.stylesContains(constants.SIGNATURE)) {
                                entry = new SignatureEntry(question, {});
                                break;
                            }
                            entry = new ImageEntry(question, {});
                            break;
                        case constants.CONTROL_AUDIO_CAPTURE:
                            entry = new AudioEntry(question, {});
                            break;
                        case constants.CONTROL_VIDEO_CAPTURE:
                            entry = new VideoEntry(question, {});
                            break;
                        // any other control types are unsupported
                    }
                }
        }
        if (!entry) {
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
        const form = formEntryUtils.getRootForm(question);
        if (form === undefined) {
            return {};
        }
        return form.displayOptions || {};
    }

    /**
     * Utility to render question as select2
     * additionalOptions is passed as object to select2 constructor
     */
    function select2ify(entry, additionalOptions, isMulti) {
        var $input = $('#' + entry.entryId);
        $input.select2(_.extend({
            allowClear: true,
            placeholder: entry.placeholderText,
            escapeMarkup: function (m) { return DOMPurify.sanitize(m); },
        }, additionalOptions));

        applySelect2Labelledby(entry.entryId, isMulti);
    }

    /**
     * Select2 ignores labelling from original `<select>` element.
     * Fix that by applying `aria-labelledby` to the element getting keyboard focus.
     */
    function applySelect2Labelledby(entryId, isMulti) {
        const $input = $('#' + entryId);
        const $focusElement = isMulti
            ? $input.parent().find('textarea.select2-search__field')
            : $input.parent().find('span.select2-selection--single');
        $focusElement.attr('aria-labelledby', entryId + '-label');
    }

    /**
     * Function to handle answer changes for entries using selct2
     */
    function select2AnswerChange(parentClass) {
        return function (newValue) {
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
        AudioEntry: AudioEntry,
        ButtonSelectEntry: ButtonSelectEntry,
        ComboboxEntry: ComboboxEntry,
        DateEntry: DateEntry,
        DropdownEntry: DropdownEntry,
        EthiopianDateEntry: EthiopianDateEntry,
        FloatEntry: FloatEntry,
        FreeTextEntry: FreeTextEntry,
        ImageEntry: ImageEntry,
        InfoEntry: InfoEntry,
        IntEntry: IntEntry,
        MultiSelectEntry: MultiSelectEntry,
        MultiDropdownEntry: MultiDropdownEntry,
        PhoneEntry: PhoneEntry,
        SingleSelectEntry: SingleSelectEntry,
        SignatureEntry: SignatureEntry,
        TimeEntry: TimeEntry,
        UnsupportedEntry: UnsupportedEntry,
        VideoEntry: VideoEntry,
    };
});
