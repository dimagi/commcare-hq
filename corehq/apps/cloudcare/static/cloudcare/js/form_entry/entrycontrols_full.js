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
    self.isValid = function(rawAnswer) {
        return self.getErrorMessage(rawAnswer) === null;
    };

    // Returns an error message given the answer. null if no error
    self.getErrorMessage = function(rawAnswer) {
        return null;
    }

    self.clear = function() {
        self.answer(Formplayer.Const.NO_ANSWER);
    };
    self.afterRender = function() {
      // Override with any logic that comes after rendering the Entry
    };
    if (self.answer) {
        self.answer.subscribe(self.onAnswerChange.bind(self));
    }
}
Entry.prototype.onAnswerChange = function(newValue) {};

// This should set the answer value if the answer is valid. If the raw answer is valid, this
// function performs any sort of processing that needs to be done before setting the answer.
Entry.prototype.onPreProcess = function(newValue) {
    if (this.isValid(newValue)) {
        this.answer(newValue);
    }
    this.question.error(this.getErrorMessage(newValue));
};

/**
 * Serves as the base for all entries that take an array answer.
 */
EntryArrayAnswer = function(question, options) {
    var self = this;
    Entry.call(self, question, options);
    self.rawAnswer = ko.observableArray(_.clone(question.answer()));

    self.rawAnswer.subscribe(self.onPreProcess.bind(self));
    self.previousAnswer = self.answer()

}
EntryArrayAnswer.prototype = Object.create(Entry.prototype);
EntryArrayAnswer.prototype.constructor = Entry;
EntryArrayAnswer.prototype.onAnswerChange = function(newValue) {
    if (Formplayer.Utils.answersEqual(this.answer(), this.previousAnswer)) {
        return;
    }
    this.question.onchange();
    this.previousAnswer = this.answer();
};
EntryArrayAnswer.prototype.onPreProcess = function(newValue) {
    var processed;
    if (this.isValid(newValue)) {
        if (newValue.length) {
            processed = _.map(newValue, function(d) { return +d });
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
EntrySingleAnswer = function(question, options) {
    var self = this;
    Entry.call(self, question, options);
    if (question.answer()) {
        self.rawAnswer = ko.observable(question.answer());
    } else {
        self.rawAnswer = ko.observable(Formplayer.Const.NO_ANSWER);
    }
    self.rawAnswer.subscribe(self.onPreProcess.bind(self));
}
EntrySingleAnswer.prototype = Object.create(Entry.prototype);
EntrySingleAnswer.prototype.constructor = Entry;
EntrySingleAnswer.prototype.onAnswerChange = function(newValue) {
    this.question.onchange();
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
    self.domain = question.domain ? question.domain() : 'full';
    self.lengthLimit = options.lengthLimit || 100000;
    self.prose = question.domain_meta ? question.domain_meta().longtext : false;

    self.isValid = function(rawAnswer) {
        var errmsg = self.getErrorMessage(rawAnswer);
        if (errmsg) {
            return false;
        }
        return true;
    }

    self.getErrorMessage = function(raw) {
        return null;
    };

    self.helpText = function() {
        return isPassword ? 'Password' : 'Free response';
    };
}
FreeTextEntry.prototype = Object.create(EntrySingleAnswer.prototype);
FreeTextEntry.prototype.constructor = EntrySingleAnswer;
FreeTextEntry.prototype.onPreProcess = function(newValue) {
    if (this.isValid(newValue)) {
        this.answer(newValue === '' ? Formplayer.Const.NO_ANSWER : newValue);
    }
    this.question.error(this.getErrorMessage(newValue));
};

/**
 * The entry that defines an integer input. Only accepts whole numbers
 */
function IntEntry(question, options) {
    var self = this;
    FreeTextEntry.call(self, question, options);
    self.templateType = 'str';
    self.lengthLimit = options.lengthLimit || 10;

    self.getErrorMessage = function(rawAnswer) {
        return (isNaN(+rawAnswer) || +rawAnswer != Math.floor(+rawAnswer) ? "Not a valid whole number" : null);
    };

    self.helpText = function() {
        return 'Number';
    };

}
IntEntry.prototype = Object.create(FreeTextEntry.prototype);
IntEntry.prototype.constructor = FreeTextEntry;

IntEntry.prototype.onPreProcess = function(newValue) {
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
    this.lengthLimit = options.lengthLimit || 15;

    this.getErrorMessage = function(rawAnswer) {
        if (rawAnswer === '') { return null; }
        return (!(/^[+\-]?\d*(\.\d+)?$/.test(rawAnswer)) ? "This does not appear to be a valid phone/numeric number" : null);
    };

    this.helpText = function() {
        return 'Phone number or Numeric ID';
    };

}
PhoneEntry.prototype = Object.create(FreeTextEntry.prototype);
PhoneEntry.prototype.constructor = FreeTextEntry;


/**
 * The entry that defines an float input. Only accepts real numbers
 */
function FloatEntry(question, options) {
    IntEntry.call(this, question, options);
    this.templateType = 'str';

    this.getErrorMessage = function(rawAnswer) {
        return (isNaN(+rawAnswer) ? "Not a valid number" : null);
    }

    this.helpText = function() {
        return 'Decimal';
    }
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

    self.onClear = function() {
        self.rawAnswer([]);
    };

    self.isValid = function(rawAnswer) {
        return _.isArray(rawAnswer);
    }
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
    self.onClear = function() { self.rawAnswer(Formplayer.Const.NO_ANSWER); };
    self.isValid = function() { return true };
}
SingleSelectEntry.prototype = Object.create(EntrySingleAnswer.prototype);
SingleSelectEntry.prototype.constructor = EntrySingleAnswer;
SingleSelectEntry.prototype.onPreProcess = function(newValue) {
    if (this.isValid(newValue)) {
        if (newValue === Formplayer.Const.NO_ANSWER) {
            this.answer(newValue);
        } else {
            this.answer(+newValue);
        }
    }
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
        maxDate;

    EntrySingleAnswer.call(self, question, options);
    // Set max date to 10 years in the future
    maxDate = moment(thisYear + 10, 'YYYY').toDate();
    // Set min date to 100 years in the past
    minDate = moment(thisYear - 100, 'YYYY').toDate();
    self.afterRender = function() {
        self.$picker = $('#' + self.entryId);
        self.$picker.datetimepicker({
            timepicker: self.timepicker,
            datepicker: self.datepicker,
            format: self.clientFormat,
            formatTime: self.clientTimeFormat,
            formatDate: self.clientDateFormat,
            value: self.answer() ? self.convertServerToClientFormat(self.answer()) : self.answer(),
            maxDate: maxDate,
            minDate: minDate,
            scrollInput: false,
            onChangeDateTime: function(newDate) {
                if (!newDate) {
                    self.answer(Formplayer.Const.NO_ANSWER);
                    return;
                }
                self.answer(moment(newDate).format(self.serverFormat));
            }
        });
    };
}
DateTimeEntryBase.prototype = Object.create(EntrySingleAnswer.prototype);
DateTimeEntryBase.prototype.constructor = EntrySingleAnswer;
DateTimeEntryBase.prototype.convertServerToClientFormat = function(date) {
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


function DateTimeEntry(question, options) {
    this.templateType = 'datetime';
    this.timepicker = true;
    this.datepicker = true;
    DateTimeEntryBase.call(this, question, options);
}
DateTimeEntry.prototype = Object.create(DateTimeEntryBase.prototype);
DateTimeEntry.prototype.constructor = DateTimeEntryBase;
DateTimeEntry.prototype.clientTimeFormat = 'HH:mm';
DateTimeEntry.prototype.clientDateFormat = 'MM/DD/YYYY';
DateTimeEntry.prototype.clientFormat = 'MM/DD/YYYY HH:mm';

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
    self.apiKey = 'https://maps.googleapis.com/maps/api/js?key=' + window.GMAPS_API_KEY + '&sensor=false';
    self.map = null;

    self.DEFAULT = {
        lat: 30,
        lon: 0,
        zoom: 1,
        anszoom: 6
    };

    self.onClear = function() {
        self.rawAnswer([]);
    };

    window.gMapsCallback = function() {
        self.geocoder = new google.maps.Geocoder();
        self.map = new google.maps.Map($('#' + self.entryId)[0], {
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            center: new google.maps.LatLng(self.DEFAULT.lat, self.DEFAULT.lon),
            zoom: self.DEFAULT.zoom
        });
        if (self.rawAnswer().length) {
            self.map.setCenter(new google.maps.LatLng(self.rawAnswer()[0], self.rawAnswer()[1]));
            self.map.setZoom(self.DEFAULT.anszoom);
        }
        google.maps.event.addListener(self.map, "center_changed", self.updateCenter.bind(self));
    }
    self.afterRender = function() {
        if (typeof google === "undefined") {
            $.getScript(self.apiKey + '&callback=gMapsCallback');
        } else {
            window.gMapsCallback();
        }
    };

    self.updateCenter = function() {
        var center = self.map.getCenter();
        self.rawAnswer([center.lat(), center.lng()]);
    };

    self.formatLat = function() {
        return self.formatCoordinate(self.rawAnswer()[0] || null, ['N', 'S']);
    };
    self.formatLon = function() {
        return self.formatCoordinate(self.rawAnswer()[1] || null, ['E', 'W']);
    };
    self.formatCoordinate = function(coordinate, cardinalities) {
        var cardinality = coordinate >= 0 ? cardinalities[0] : cardinalities [1];
        if (coordinate !== null) {
            return cardinality + intpad(intpad(Math.abs(coordinate).toFixed(5), 8));
        }
        return '??.?????';
    };

    self.search = function(form) {
        var query = $(form).find('.query').val();
        self.geocoder.geocode({
            'address': query
        }, function(results, status) {
            if (status === google.maps.GeocoderStatus.OK) {
                self.map.fitBounds(results[0].geometry.viewport);
                self.map.setCenter(results[0].geometry.location);
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
    var rawStyle;

    switch (question.datatype()) {
        case Formplayer.Const.STRING:
            rawStyle = question.style ? ko.utils.unwrapObservable(question.style.raw) === 'numeric' : false;
            if (rawStyle) {
                entry = new PhoneEntry(question, {});
            } else {
                entry = new FreeTextEntry(question, {});
            }
            break;
        case Formplayer.Const.INT:
            entry = new IntEntry(question, {});
            break;
        case Formplayer.Const.LONGINT:
            entry = new IntEntry(question, { lengthLimit: 15 });
            break;
        case Formplayer.Const.FLOAT:
            entry = new FloatEntry(question, {});
            break;
        case Formplayer.Const.SELECT:
            entry = new SingleSelectEntry(question, {});
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
        case Formplayer.Const.DATETIME:
            entry = new DateTimeEntry(question, {});
            break;
        case Formplayer.Const.GEO:
            entry = new GeoPointEntry(question, {});
            break;
        case Formplayer.Const.INFO:
            entry = new InfoEntry(question, {});
            break;
        default:
            console.warn('No active entry for: ' + question.datatype());
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
