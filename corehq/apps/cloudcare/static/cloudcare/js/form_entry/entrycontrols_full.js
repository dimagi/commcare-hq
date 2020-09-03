/* globals Formplayer, EntrySingleAnswer, moment */

/**
 * Import vars sent from server
 */
var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
var MAPBOX_ACCESS_TOKEN = initialPageData("mapbox_access_token");



/**
 * The base Object for all entries. Each entry takes a question object and options
 * @param {Object} question - A question object
 * @param {Object} object - A hash of different options
 */
function Entry(question, options) {
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
    self.getErrorMessage = function (rawAnswer) {
        return null;
    };

    self.clear = function () {
        self.answer(Formplayer.Const.NO_ANSWER);
    };
    self.afterRender = function () {
        // Override with any logic that comes after rendering the Entry
    };
    if (self.answer) {
        self.answer.subscribe(self.onAnswerChange.bind(self));
    }
}
Entry.prototype.onAnswerChange = function (newValue) {};

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
EntryArrayAnswer = function (question, options) {
    var self = this;
    Entry.call(self, question, options);
    self.rawAnswer = ko.observableArray(_.clone(question.answer()));

    self.rawAnswer.subscribe(self.onPreProcess.bind(self));
    self.previousAnswer = self.answer();

};
EntryArrayAnswer.prototype = Object.create(Entry.prototype);
EntryArrayAnswer.prototype.constructor = Entry;
EntryArrayAnswer.prototype.onAnswerChange = function (newValue) {
    if (Formplayer.Utils.answersEqual(this.answer(), this.previousAnswer)) {
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
            processed = Formplayer.Const.NO_ANSWER;
        }

        if (!Formplayer.Utils.answersEqual(processed, this.answer())) {
            this.previousAnswer = this.answer();
            this.answer(processed);
        }
    }
    self.previousAnswer = null;
};


/**
 * Serves as the base for all entries that take an answer that is not an array.
 */
EntrySingleAnswer = function (question, options) {
    var self = this;

    var getRawAnswer = function (answer) {
        // Zero is a perfectly valid answer
        if (answer !== 0 && !answer) {
            return Formplayer.Const.NO_ANSWER;
        }
        return answer;
    };

    Entry.call(self, question, options);
    self.valueUpdate = undefined;
    self.rawAnswer = ko.observable(getRawAnswer(question.answer()));
    self.placeholderText = '';

    self.rawAnswer.subscribe(self.onPreProcess.bind(self));

    if (options.enableAutoUpdate) {
        self.valueUpdate = 'keyup';
        self.answer.extend({
            rateLimit: {
                timeout: Formplayer.Const.KO_ENTRY_TIMEOUT,
                method: "notifyWhenChangesStop",
            },
        });
    }

};
EntrySingleAnswer.prototype = Object.create(Entry.prototype);
EntrySingleAnswer.prototype.constructor = Entry;
EntrySingleAnswer.prototype.onAnswerChange = function (newValue) {
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
                if (message === Formplayer.Const.NO_ANSWER) {
                    self.rawAnswer(Formplayer.Const.NO_ANSWER);
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
        self.rawAnswer(Formplayer.Const.NO_ANSWER);
    }
};


/**
 * An entry that represent a question label.
 */
function InfoEntry(question, options) {
    var self = this;
    Entry.call(self, question, options);
    self.templateType = 'blank';
}

InfoEntry.prototype = Object.create(Entry.prototype);
InfoEntry.prototype.constructor = Entry;


/**
 * The entry used when we have an unidentified entry
 */
function UnsupportedEntry(question, options) {
    var self = this;
    Entry.call(self, question, options);
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
    var isPassword = ko.utils.unwrapObservable(question.control) === Formplayer.Const.CONTROL_SECRET;
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

    self.getErrorMessage = function (raw) {
        return null;
    };

    self.helpText = function () {
        if (isPassword) {
            return gettext('Password');
        }
        switch (self.datatype) {
            case Formplayer.Const.BARCODE:
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
        this.answer(newValue === '' ? Formplayer.Const.NO_ANSWER : newValue);
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
            var broadcastObj = {
                full: item.place_name,
            };
            item.context.forEach(function (contextValue) {
                try {
                    if (contextValue.id.startsWith('postcode')) {
                        broadcastObj.zipcode = contextValue.text;
                    } else if (contextValue.id.startsWith('place')) {
                        broadcastObj.city = contextValue.text;
                    } else if (contextValue.id.startsWith('country')) {
                        broadcastObj.country = contextValue.text;
                        if (contextValue.short_code) {
                            broadcastObj.country_short = contextValue.short_code;
                        }
                    } else if (contextValue.id.startsWith('region')) {
                        broadcastObj.region = contextValue.text;
                        // TODO: Deprecate state_short and state_long.
                        broadcastObj.state_long = contextValue.text;
                        if (contextValue.short_code) {
                            broadcastObj.state_short = contextValue.short_code.replace('US-', '');
                        }
                        // If US region, it's actually a state so add us_state.
                        if (contextValue.short_code && contextValue.short_code.startsWith('US-')) {
                            broadcastObj.us_state = contextValue.text;
                            broadcastObj.us_state_short = contextValue.short_code.replace('US-', '');
                        }
                    }
                } catch (err) {
                    // Swallow error, broadcast best effort. Consider logging.
                }
            });
            // street composed of (optional) number and street name.
            broadcastObj.street = item.address || '';
            broadcastObj.street += ' ' + item.text;

            question.parentPubSub.notifySubscribers(broadcastObj, broadcastTopic);
        });
        // The default full address returned to the search bar
        return item.place_name;
    };

    // geocoder function called when user presses 'x', broadcast a no answer to subscribers.
    self.geocoderOnClearCallback = function () {
        self.rawAnswer(Formplayer.Const.NO_ANSWER);
        self.question.error(null);
        self.editing = true;
        self.broadcastTopics.forEach(function (broadcastTopic) {
            question.parentPubSub.notifySubscribers(Formplayer.Const.NO_ANSWER, broadcastTopic);
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

        var defaultGeocoderLocation = initialPageData('default_geocoder_location') || {};
        var geocoder = new MapboxGeocoder({
            accessToken: MAPBOX_ACCESS_TOKEN,
            types: 'address',
            enableEventLogging: false,
            getItemValue: self.geocoderItemCallback,
        });
        if (defaultGeocoderLocation.coordinates) {
            geocoder.setProximity(defaultGeocoderLocation.coordinates);
        }
        geocoder.on('clear', self.geocoderOnClearCallback);
        geocoder.addTo('#' + self.entryId);
        // Must add the form-control class to the input created by mapbox in order to edit.
        var inputEl = $('input.mapboxgl-ctrl-geocoder--input');
        inputEl.addClass('form-control');
        inputEl.on('keydown', _.debounce(self._inputOnKeyDown, 200));
    };

    self._inputOnKeyDown = function (event) {
        // On key down, switch to editing mode so we unregister an answer.
        if (!self.editing && self.rawAnswer() !== event.target.value) {
            self.rawAnswer(Formplayer.Const.NO_ANSWER);
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
    self.lengthLimit = options.lengthLimit || Formplayer.Const.INT_LENGTH_LIMIT;
    var valueLimit = options.valueLimit || Formplayer.Const.INT_VALUE_LIMIT;

    self.getErrorMessage = function (rawAnswer) {
        if (isNaN(+rawAnswer) || +rawAnswer !== Math.floor(+rawAnswer))
            return gettext("Not a valid whole number");
        if (+rawAnswer > valueLimit)
            return gettext("Number is too large");
        return null;
    };

    self.helpText = function () {
        return 'Number';
    };

    self.enableReceiver(question, options);
}
IntEntry.prototype = Object.create(FreeTextEntry.prototype);
IntEntry.prototype.constructor = FreeTextEntry;

IntEntry.prototype.onPreProcess = function (newValue) {
    if (this.isValid(newValue)) {
        if (newValue === '') {
            this.answer(Formplayer.Const.NO_ANSWER);
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
        return (!(/^[+\-]?\d*(\.\d+)?$/.test(rawAnswer)) ? "This does not appear to be a valid phone/numeric number" : null);
    };

    this.helpText = function () {
        return 'Phone number or Numeric ID';
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
    this.lengthLimit = options.lengthLimit || Formplayer.Const.FLOAT_LENGTH_LIMIT;
    var valueLimit = options.valueLimit || Formplayer.Const.FLOAT_VALUE_LIMIT;

    this.getErrorMessage = function (rawAnswer) {
        if (isNaN(+rawAnswer))
            return gettext("Not a valid number");
        if (+rawAnswer > valueLimit)
            return gettext("Number is too large");
        return null;
    };

    this.helpText = function () {
        return 'Decimal';
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
 * Represents multiple radio button entries
 */
function SingleSelectEntry(question, options) {
    var self = this;
    EntrySingleAnswer.call(this, question, options);
    self.choices = question.choices;
    self.templateType = 'select';
    self.isMulti = false;
    self.onClear = function () {
        self.rawAnswer(Formplayer.Const.NO_ANSWER);
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
        if (newValue === Formplayer.Const.NO_ANSWER) {
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
    self.rawAnswer(Formplayer.Const.NO_ANSWER);
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
        var colWidth = parseInt(12 / self.choices().length) || 1;
        return 'col-xs-' + colWidth;
    });

    self.onClear = function () {
        self.rawAnswer(Formplayer.Const.NO_ANSWER);
    };
    self.isValid = function () {
        return true;
    };
}
ChoiceLabelEntry.prototype = Object.create(EntrySingleAnswer.prototype);
ChoiceLabelEntry.prototype.constructor = EntrySingleAnswer;
ChoiceLabelEntry.prototype.onPreProcess = function (newValue) {
    if (this.isValid(newValue)) {
        if (newValue === Formplayer.Const.NO_ANSWER) {
            this.answer(newValue);
        } else {
            this.answer(+newValue);
        }
    }
};

function DropdownEntry(question, options) {
    var self = this;
    EntrySingleAnswer.call(this, question, options);
    self.templateType = 'dropdown';

    self.options = ko.pureComputed(function () {
        return _.map(question.choices(), function (choice, idx) {
            return {
                text: choice,
                idx: idx + 1,
            };
        });
    });
}
DropdownEntry.prototype = Object.create(EntrySingleAnswer.prototype);
DropdownEntry.prototype.constructor = EntrySingleAnswer;
DropdownEntry.prototype.onPreProcess = function (newValue) {
    // When newValue is undefined it means we've unset the select question.
    if (newValue === Formplayer.Const.NO_ANSWER || newValue === undefined) {
        this.answer(Formplayer.Const.NO_ANSWER);
    } else {
        this.answer(+newValue);
    }
};

/**
 * The ComboboxEntry is an advanced android formatting entry. It is enabled
 * when the user specifies combobox in the appearance attributes for a
 * single select question.
 *
 * Docs: https://confluence.dimagi.com/display/commcarepublic/Advanced+CommCare+Android+Formatting#AdvancedCommCareAndroidFormatting-SingleSelect"ComboBox"
 */
function ComboboxEntry(question, options) {
    var self = this,
        initialOption;
    EntrySingleAnswer.call(this, question, options);

    // Specifies the type of matching we will do when a user types a query
    self.matchType = options.matchType;
    self.lengthLimit = Infinity;
    self.templateType = 'str';
    self.placeholderText = gettext('Type to filter answers');

    self.options = ko.computed(function () {
        return _.map(question.choices(), function (choice, idx) {
            return {
                name: choice,
                id: idx + 1,
            };
        });
    });
    self.options.subscribe(function () {
        self.renderAtwho();
        if (!self.isValid(self.rawAnswer())) {
            self.question.error(gettext('Not a valid choice'));
        }
    });
    self.helpText = function () {
        return 'Combobox';
    };

    // If there is a prexisting answer, set the rawAnswer to the corresponding text.
    if (question.answer()) {
        initialOption = self.options()[self.answer() - 1];
        self.rawAnswer(
            initialOption ? initialOption.name : Formplayer.Const.NO_ANSWER
        );
    }

    self.renderAtwho = function () {
        var $input = $('#' + self.entryId),
            limit = Infinity,
            $atwhoView;
        $input.atwho('destroy');
        $input.atwho('setIframe', window.frameElement, true);
        $input.atwho({
            at: '',
            data: self.options(),
            maxLen: Infinity,
            tabSelectsMatch: false,
            limit: limit,
            suffix: '',
            callbacks: {
                filter: function (query, data) {
                    var results = _.filter(data, function (item) {
                        return ComboboxEntry.filter(query, item, self.matchType);
                    });
                    $atwhoView = $('.atwho-container .atwho-view');
                    $atwhoView.attr({
                        'data-message': 'Showing ' + Math.min(limit, results.length) + ' of ' + results.length,
                    });
                    return results;
                },
                matcher: function () {
                    return $input.val();
                },
                sorter: function (query, data) {
                    return data;
                },
            },
        });
    };
    self.isValid = function (value) {
        if (!value) {
            return true;
        }
        return _.include(
            _.map(self.options(), function (option) {
                return option.name;
            }),
            value
        );
    };

    self.afterRender = function () {
        self.renderAtwho();
    };

    self.enableReceiver(question, options);
}

ComboboxEntry.filter = function (query, d, matchType) {
    var match;
    if (matchType === Formplayer.Const.COMBOBOX_MULTIWORD) {
        // Multiword filter, matches any choice that contains all of the words in the query
        //
        // Assumption is both query and choice will not be very long. Runtime is O(nm)
        // where n is number of words in the query, and m is number of words in the choice
        var wordsInQuery = query.split(' ');
        var wordsInChoice = d.name.split(' ');

        match = _.all(wordsInQuery, function (word) {
            return _.include(wordsInChoice, word);
        });
    } else if (matchType === Formplayer.Const.COMBOBOX_FUZZY) {
        // Fuzzy filter, matches if query is "close" to answer
        match = (
            (window.Levenshtein.get(d.name.toLowerCase(), query.toLowerCase()) <= 2 && query.length > 3) ||
            d.name.toLowerCase() === query.toLowerCase()
        );
    }

    // If we've already matched, return true
    if (match) {
        return true;
    }

    // Standard filter, matches only start of word
    return d.name.toLowerCase().startsWith(query.toLowerCase());
};

ComboboxEntry.prototype = Object.create(EntrySingleAnswer.prototype);
ComboboxEntry.prototype.constructor = EntrySingleAnswer;
ComboboxEntry.prototype.onPreProcess = function (newValue) {
    var value;
    if (newValue === Formplayer.Const.NO_ANSWER || newValue === '') {
        this.answer(Formplayer.Const.NO_ANSWER);
        this.question.error(null);
        return;
    }

    value = _.find(this.options(), function (d) {
        return d.name === newValue;
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
            if (option.name === message[fieldByPriority]) {
                self.rawAnswer(option.name);
                return;
            }
        }
    }
    // no options match message[field]
    self.rawAnswer(Formplayer.Const.NO_ANSWER);
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
                    self.answer(Formplayer.Const.NO_ANSWER);
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
                        .show().text(django.gettext('Save'))
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


function GeoPointEntry(question, options) {
    var self = this;
    EntryArrayAnswer.call(self, question, options);
    self.templateType = 'geo';
    self.map = null;

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
        if (MAPBOX_ACCESS_TOKEN) {
            self.map = L.map(self.entryId).setView([self.DEFAULT.lat, self.DEFAULT.lon], self.DEFAULT.zoom);
            L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token='
                        + MAPBOX_ACCESS_TOKEN, {
                id: 'mapbox/streets-v11',
                attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                             ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            }).addTo(self.map);
            self.map.on('move', self.updateCenter);

            self.centerMarker = L.marker(self.map.getCenter()).addTo(self.map);

            L.mapbox.accessToken = MAPBOX_ACCESS_TOKEN;
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
    var entry = null;
    var options = {};
    var isNumeric = false;
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
        case Formplayer.Const.STRING:
            // Barcode uses text box for CloudCare so it's possible to still enter a barcode field
        case Formplayer.Const.BARCODE:
            // If it's a receiver, it cannot autoupdate because updates will come quickly which messes with the
            // autoupdate rate limiting.
            if (receiveStyle) {
                options.receiveStyle = receiveStyle;
            } else {
                options.enableAutoUpdate = isPhoneMode;
            }
            if (question.stylesContains(Formplayer.Const.ADDRESS)) {
                entry = new AddressEntry(question, {
                    broadcastStyles: question.stylesContaining(/broadcast-*/),
                });
            } else if (question.stylesContains(Formplayer.Const.NUMERIC)) {
                entry = new PhoneEntry(question, options);
            } else {
                entry = new FreeTextEntry(question, options);
            }
            break;
        case Formplayer.Const.INT:
            entry = new IntEntry(question, {
                enableAutoUpdate: isPhoneMode,
            });
            break;
        case Formplayer.Const.LONGINT:
            entry = new IntEntry(question, {
                lengthLimit: Formplayer.Const.LONGINT_LENGTH_LIMIT,
                valueLimit: Formplayer.Const.LONGINT_VALUE_LIMIT,
                enableAutoUpdate: isPhoneMode,
            });
            break;
        case Formplayer.Const.FLOAT:
            entry = new FloatEntry(question, {
                enableAutoUpdate: isPhoneMode,
            });
            break;
        case Formplayer.Const.SELECT:
            isMinimal = style === Formplayer.Const.MINIMAL;
            if (style) {
                isCombobox = question.stylesContains(Formplayer.Const.COMBOBOX);
            }
            if (style) {
                isLabel = style === Formplayer.Const.LABEL || style === Formplayer.Const.LIST_NOLABEL;
                hideLabel = style === Formplayer.Const.LIST_NOLABEL;
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
        case Formplayer.Const.MULTI_SELECT:
            entry = new MultiSelectEntry(question, {});
            break;
        case Formplayer.Const.DATE:
            entry = new DateEntry(question, {});
            break;
        case Formplayer.Const.TIME:
            entry = new TimeEntry(question, {});
            break;
        case Formplayer.Const.GEO:
            entry = new GeoPointEntry(question, {});
            break;
        case Formplayer.Const.INFO:
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
