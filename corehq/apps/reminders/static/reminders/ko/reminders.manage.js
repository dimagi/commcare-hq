var ManageRemindersViewModel = function (initial, choices, ui_type, available_languages) {
    'use strict';
    var self = this;

    self.choices = choices || {};
    self.ui_type = ui_type;

    self.available_languages = ko.observable(_.map(available_languages, function (langcode) {
        console.log(langcode);
        return new ReminderLanguage(langcode, langcode);
    }));
    self.default_lang = ko.observable(initial.default_lang);

    self.start_reminder_on = ko.observable(initial.start_reminder_on);
    self.isStartReminderCaseProperty = ko.computed(function () {
        return self.start_reminder_on() === self.choices.START_REMINDER_ON_CASE_PROPERTY;
    });
    self.isStartReminderCaseDate = ko.computed(function () {
        return self.start_reminder_on() === self.choices.START_REMINDER_ON_CASE_DATE;
    });

    self.start_match_type = ko.observable(initial.start_match_type);
    self.isStartMatchValueVisible = ko.computed(function () {
        return self.start_match_type() !== self.choices.MATCH_ANY_VALUE;
    });

    self.start_property_offset_type = ko.observable(initial.start_property_offset_type);
    self.isStartPropertyOffsetVisible = ko.computed(function () {
        return self.start_property_offset_type() !== self.choices.START_PROPERTY_OFFSET_IMMEDIATE;
    });

    self.recipient = ko.observable(initial.recipient);
    self.isRecipientSubcase = ko.computed(function () {
        return self.recipient() === self.choices.RECIPIENT_SUBCASE;
    });

    self.recipient_case_match_type = ko.observable(initial.recipient_case_match_type);
    self.isRecipientCaseValueVisible = ko.computed(function () {
        return self.recipient_case_match_type() !== self.choices.MATCH_ANY_VALUE;
    });

    self.method = ko.observable(initial.method);
    self.eventObjects = ko.observable();
    self.events = ko.computed(function () {
        return JSON.stringify(_.map(self.eventObjects(), function (event){
            return event.asJSON();
        }));
    });
    self.event_timing = ko.observable(initial.event_timing);

    self.event_interpretation = ko.computed(function () {
        var event_timing = $.parseJSON(self.event_timing());
        return event_timing.event_interpretation;
    });

    self.repeat_type = ko.observable(initial.repeat_type);
    self.isScheduleLengthVisible = ko.computed(function () {
        return self.repeat_type() !== self.choices.REPEAT_TYPE_NO;
    });
    self.isMaxIterationCountVisible = ko.computed(function () {
        return self.repeat_type() === self.choices.REPEAT_TYPE_SPECIFIC;
    });

    self.stop_condition = ko.observable(initial.stop_condition);
    self.isUntilVisible = ko.computed(function () {
        return self.stop_condition() === self.choices.STOP_CONDITION_CASE_PROPERTY;
    });

    self.init = function () {
        var events = $.parseJSON(initial.events || '[]');
        if (self.ui_type === self.choices.UI_SIMPLE_FIXED) {
            // only use the first event in the list
            events = [events[0]];
        }
        self.eventObjects(_.map(events, function (event) {
            return new ReminderEvent(
                event,
                self.choices,
                self.method,
                self.event_timing,
                self.event_interpretation,
                self.available_languages
            );
        }));
    }

};

var ReminderEvent = function (eventData, choices, method, event_timing, event_interpretation, available_languages) {
    'use strict';
    var self = this;
    self.choices = choices;
    self.method = method;
    self.event_timing = event_timing;
    self.event_interpretation = event_interpretation;
    self.available_languages = available_languages;

    self.fire_time_type = ko.computed(function () {
        var event_timing = $.parseJSON(self.event_timing());
        return event_timing.fire_time_type;
    });

    self.isEventImmediate = ko.computed(function () {
        var event_timing = $.parseJSON(self.event_timing());
        return event_timing.special === self.choices.EVENT_TIMING_IMMEDIATE;
    });

    self.day_num = ko.observable(eventData.day_num);

    self.fire_time = ko.observable(eventData.fire_time);
    self.isFireTimeVisible = ko.computed(function () {
        return ((self.fire_time_type() === self.choices.FIRE_TIME_DEFAULT) && !self.isEventImmediate())
            || self.fire_time_type() === self.choices.FIRE_TIME_RANDOM;
    });

    self.fire_time_aux = ko.observable(eventData.fire_time_aux);
    self.isFireTimeAuxVisible = ko.computed(function () {
        return self.fire_time_type() === self.choices.FIRE_TIME_CASE_PROPERTY;
    });

    self.time_window_length = ko.observable(eventData.time_window_length);
    self.isWindowLengthVisible = ko.computed(function () {
        return self.fire_time_type() === self.choices.FIRE_TIME_RANDOM;
    });

    self.callback_timeout_intervals = ko.observable(eventData.callback_timeout_intervals);
    self.isCallbackTimeoutsVisible = ko.computed(function () {
        return self.method() === self.choices.METHOD_SMS_CALLBACK;
    });

    self.form_unique_id = ko.observable(eventData.form_unique_id);
    self.isSurveyVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_SMS_SURVEY)
            || (self.method() === self.choices.METHOD_IVR_SURVEY);
    });

    self.message_data = ko.observable();
    self.messageTranslations = ko.observable(_.map(eventData.message, function (message, language) {
        return new ReminderMessage(message, language, self.available_languages);
    }));
    self.messageByLangcode = ko.computed(function () {
        var translations = {},
            available_langcodes = _.map(self.available_languages(), function (lang) {
                return lang.langcode();
            });
        _.each(self.messageTranslations(), function (message) {
            translations[message.language()] = message;
        });
        _.each(_.difference(available_langcodes, _(translations).keys()), function(lang) {
            var existingTranslations = self.messageTranslations(),
                newMessage = new ReminderMessage("", lang, self.available_languages);
            existingTranslations.push(newMessage);
            translations[lang] = newMessage;
            self.messageTranslations(existingTranslations);
        });
        return translations;
    });
    self.isMessageVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_SMS)
            || (self.method() === self.choices.METHOD_SMS_CALLBACK);
    });

    self.asJSON = ko.computed(function () {
        return {
            fire_time_type: self.fire_time_type(),
            fire_time_aux: self.fire_time_aux(),
            day_num: self.day_num(),
            fire_time: self.fire_time(),
            form_unique_id: self.form_unique_id(),
            message: self.message_data(),
            callback_timeout_intervals: self.callback_timeout_intervals(),
            time_window_length: self.time_window_length()
        }
    });
};

var ReminderMessage = function (message, language, available_languages) {
    'use strict';
    var self = this;
    self.language = ko.observable(language);
    self.message = ko.observable(message);
    self.available_languages = available_languages;


    self.languageLabel = ko.computed(function () {
        if (self.available_languages().length == 1) {
            return "";
        }
        var language_name = self.language();
        _.each(self.available_languages(), function (lang) {
            if (lang.langcode() === self.language()) {
                language_name = lang.name();
            }
        });
        return '(' + language_name + ')';
    });
};

var ReminderLanguage = function (langcode, name) {
    'use strict';
    var self = this;
    self.langcode = ko.observable(langcode);
    self.name = ko.observable(name);
};
