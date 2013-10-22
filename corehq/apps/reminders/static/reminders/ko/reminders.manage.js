var ManageRemindersViewModel = function (
    initial,
    choices,
    ui_type,
    available_languages,
    select2_fields
) {
    'use strict';
    var self = this;

    self.choices = choices || {};
    self.ui_type = ui_type;
    self.select2_fields = select2_fields;

    self.case_type = ko.observable(initial.case_type);

    self.available_languages = ko.observable(_.map(available_languages, function (langcode) {
        return new ReminderLanguage(langcode);
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
    self.isStopConditionVisible = ko.computed(function () {
        return self.repeat_type() !== self.choices.REPEAT_TYPE_NO;
    });
    self.isUntilVisible = ko.computed(function () {
        return self.stop_condition() === self.choices.STOP_CONDITION_CASE_PROPERTY;
    });

    self.isMaxQuestionRetriesVisible = ko.computed(function () {
        return self.method() === self.choices.METHOD_IVR_SURVEY;
    });

    self.isForceSurveysToUsedTriggeredCaseVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_IVR_SURVEY ||
                self.method() === self.choices.METHOD_SMS_SURVEY);
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
        _.each(self.select2_fields, function (field) {
            self.initCasePropertyChoices(field);
        });
        $('[data-timeset="true"]').each(function () {
            $(this).timepicker({
                showMeridian: false,
                showSeconds: true,
                defaultTime: $(this).val() || false
            });
        });
        $('[name="form_unique_id"]').select2({
            minimumInputLength: 0,
            allowClear: true,
            ajax: {
                quietMillis: 150,
                url: '',
                dataType: 'json',
                type: 'post',
                data: function (term) {
                    return {
                        action: 'search_forms',
                        term: term
                    };
                },
                results: function (data) {
                    return {
                        results: data
                    };
                }
            },
            initSelection : function (element, callback) {
                if (element.val()) {
                    try {
                        var data = $.parseJSON(element.val());
                        callback(data);
                    } catch (e) {
                        // pass
                    }
                }
            },
            formatNoMatches: function (term) {
                return "Please create a survey first.";
            }
        });
    };

    self.addLanguage = function (langcode) {
        var currentLangcodes = _.map(self.available_languages(), function (lang) {
            return lang.langcode();
        });
        if (currentLangcodes.indexOf(langcode) === -1) {
            var availableLangs = self.available_languages();
            availableLangs.push(new ReminderLanguage(langcode));
            self.available_languages(availableLangs);
        }
        self.default_lang(langcode);
    };

    self.initCasePropertyChoices = function (field) {
        var fieldInput = $('[name="' + field.name + '"]');
        fieldInput.select2({
            minimumInputLength: 0,
            allowClear: true,
            ajax: {
                quietMillis: 150,
                url: '',
                dataType: 'json',
                type: 'post',
                data: function (term) {
                    return {
                        action: field.action,
                        caseType: self.case_type(),
                        term: term
                    };
                },
                results: function (data) {
                    return {
                        results: data
                    };
                }
            },
            createSearchChoice: function (term, data) {
                if (!self.case_type() && field.name !== 'case_type'){
                    return false;
                }
                var matching_choices = _(data).map(function (item) {
                    return item.id;
                });
                if (matching_choices.indexOf(term) === -1 && term) {
                    var cleaned_term = term.split(' ').join('_');
                    return {id: cleaned_term, text: cleaned_term, isNew: true}
                }
            },
            formatResult: function (res) {
                if (res.isError) {
                    return '<span class="label label-important">Error</span> ' + res.errorText;
                }
                if (res.isNew) {
                    return '<span class="label label-success">New</span> ' + res.text;
                }
                return res.text;
            },
            formatNoMatches: function (term) {
                if (!self.case_type() && field.name !== 'case_type') {
                    return "Please specify a Case Type";
                }
            },
            initSelection : function (element, callback) {
                if (element.val()) {
                    var data = {id: element.val(), text: element.val()};
                    callback(data);
                }
            }
        });
    };
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

    self.time_window_length = ko.observable(eventData.time_window_length || "");
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
    self.message_data = ko.computed(function () {
        var message_data = {};
        _.each(self.messageTranslations(), function (translation) {
            message_data[translation.language()] = translation.message();
        });
        return message_data;
    });
    self.isMessageVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_SMS)
            || (self.method() === self.choices.METHOD_SMS_CALLBACK);
    });

    self.asJSON = ko.computed(function () {
        return {
            fire_time_type: self.fire_time_type(),
            fire_time_aux: self.fire_time_aux(),
            is_immediate: self.isEventImmediate(),
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

    self.messageLength = ko.computed(function () {
        return self.message().length;
    });
    self.totalMessages = ko.computed(function () {
        return Math.ceil(self.messageLength()/160);
    });
    self.isMessageLong = ko.computed(function () {
        return self.totalMessages() > 1;
    });
    self.isSingleMessage = ko.computed(function () {
        return self.totalMessages() === 1;
    });
    self.showSingularChar = ko.computed(function () {
        return self.messageLength() === 1;
    });
    self.showPluralChar = ko.computed(function () {
        return !self.showSingularChar();
    });

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

var ReminderLanguage = function (langcode) {
    'use strict';
    var self = this;
    self.langcode = ko.observable(langcode);
    self.name = ko.observable(langcode);
    $.getJSON('/langcodes/langs.json', {term: self.langcode()}, function (res) {
        var index = _.map(res, function(r) { return r.code; }).indexOf(self.langcode());
        if (index >= 0) {
            self.name(res[index].name);
        }
    });
};
