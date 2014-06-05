var ManageRemindersViewModel = function (
    initial,
    choices,
    ui_type,
    available_languages,
    select2_fields,
    initial_event_template
) {
    'use strict';
    var self = this;

    self.choices = choices || {};
    self.ui_type = ui_type;
    self.select2_fields = select2_fields;
    self.initial_event_template = initial_event_template;

    self.case_type = ko.observable(initial.case_type);

    self.default_lang = ko.observable(initial.default_lang);
    self.available_languages = ko.observableArray(_.map(available_languages, function (langcode) {
        return new ReminderLanguage(langcode, self.default_lang);
    }));

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
    self.isRecipientGroup = ko.computed(function () {
        return self.recipient() === self.choices.RECIPIENT_USER_GROUP;
    });

    self.recipient_case_match_type = ko.observable(initial.recipient_case_match_type);
    self.isRecipientCaseValueVisible = ko.computed(function () {
        return self.recipient_case_match_type() !== self.choices.MATCH_ANY_VALUE;
    });

    self.method = ko.observable(initial.method);
    self.eventObjects = ko.observableArray();
    self.events = ko.computed(function () {
        return JSON.stringify(_.map(self.eventObjects(), function (event){
            return event.asJSON();
        }));
    });
    self.event_timing = ko.observable(initial.event_timing);
    self.isEventDeleteButtonVisible = ko.computed(function () {
        return self.eventObjects().length > 1;
    });

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

    self.isMaxQuestionRetriesVisible = ko.computed(function () {
        return self.method() === self.choices.METHOD_IVR_SURVEY;
    });

    self.isForceSurveysToUsedTriggeredCaseVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_IVR_SURVEY ||
                self.method() === self.choices.METHOD_SMS_SURVEY);
    });

    self.global_timeouts = ko.observable();
    self.isGlobalTimeoutsVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_SMS_CALLBACK ||
                self.method() === self.choices.METHOD_IVR_SURVEY ||
                self.method() === self.choices.METHOD_SMS_SURVEY);
    });

    self.submit_partial_forms = ko.observable(initial.submit_partial_forms);
    self.isPartialSubmissionsVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_IVR_SURVEY ||
                self.method() === self.choices.METHOD_SMS_SURVEY);
    });

    self.use_custom_content_handler = ko.observable(initial.use_custom_content_handler);

    self.init = function () {
        var events = $.parseJSON(initial.events || '[]');
        if (self.ui_type === self.choices.UI_SIMPLE_FIXED) {
            // only use the first event in the list
            events = [events[0]];
        }
        self.global_timeouts(events[0].callback_timeout_intervals);
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
        self.refreshEventsListUI();

        _.each(self.select2_fields, function (field) {
            self.initCasePropertyChoices(field);
        });

        self.languagePicker.init();
    };

    self.addLanguage = function (langcode) {
        var currentLangcodes = _.map(self.available_languages(), function (lang) {
            return lang.langcode();
        });
        if (currentLangcodes.indexOf(langcode) === -1) {
            var newLanguage = new ReminderLanguage(langcode, self.default_lang);
            self.available_languages.push(newLanguage);
             _(self.eventObjects()).each(function (event) {
                event.addTranslation(newLanguage.langcode());
            });
        }
        self.default_lang(langcode);
    };

    self.removeLanguage = function (reminderLang) {
        self.available_languages.remove(reminderLang);
        _(self.eventObjects()).each(function (event) {
            event.removeTranslation(reminderLang.langcode());
        });
    };

    self.languagePicker = new LanguagePickerViewModel(self.addLanguage);

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

    self.addEvent = function () {
        var newEventTemplate = self.initial_event_template;
        _(self.available_languages()).each(function (language) {
            newEventTemplate.message[language.langcode()] = "";
        });
        self.eventObjects.push(new ReminderEvent(
            newEventTemplate,
            self.choices,
            self.method,
            self.event_timing,
            self.event_interpretation,
            self.available_languages
        ));
    };

    self.removeEvent = function (event) {
        self.eventObjects.remove(event);
        self.refreshEventsListUI();
    };

    self.refreshEventsListUI = function () {
        $('.event-help-text').hqHelp();
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
};

var ReminderEvent = function (
    eventData,
    choices,
    method,
    event_timing,
    event_interpretation,
    available_languages
) {
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

    self.form_unique_id = ko.observable(eventData.form_unique_id);
    self.isSurveyVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_SMS_SURVEY)
            || (self.method() === self.choices.METHOD_IVR_SURVEY);
    });

    self.messageTranslations = ko.observableArray(_(eventData.message).map(function (message, langcode) {
        return new ReminderMessage(message, langcode, self.available_languages);
    }));

    // To make sure we don't lose any user-entered text by surprise
    self.removedMessageTranslations = ko.observableArray();

    self.messageByLangcode = ko.computed(function () {
        var translations = {};
        _.each(self.messageTranslations(), function (message) {
            translations[message.langcode()] = message;
        });
        return translations;
    });

    self.message_data = ko.computed(function () {
        var message_data = {};
        _.each(self.messageTranslations(), function (translation) {
            message_data[translation.langcode()] = translation.message();
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
            time_window_length: self.time_window_length()
        }
    });

    self.addTranslation = function (langcode) {
        var messagesToAdd = _(self.removedMessageTranslations()).map(function (message) {
            return message.langcode() === langcode;
        });
        if (messagesToAdd.length === 0) {
            self.messageTranslations.push(new ReminderMessage("", langcode, self.available_languages));
        } else {
            _(messagesToAdd).each(function (message) {
                self.removedMessageTranslations.remove(message);
                self.messageTranslations.push(message);
            });
        }
    };

    self.removeTranslation = function (langcode) {
        var messagesToRemove = _(self.messageTranslations()).filter(function (message) {
            return message.langcode() === langcode;
        });
        _(messagesToRemove).each(function (message) {
            self.messageTranslations.remove(message);
            self.removedMessageTranslations.push(message);
        });
    };
};

var ReminderMessage = function (message, langcode, available_languages) {
    'use strict';
    var self = this;
    self.langcode = ko.observable(langcode);
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
        var languageName = self.langcode();
        _.each(self.available_languages(), function (lang) {
            if (lang.langcode() === self.langcode()) {
                languageName = lang.name();
            }
        });
        return languageName;
    });
};

var ReminderLanguage = function (langcode, default_lang) {
    'use strict';
    var self = this;

    self.langcode = ko.observable(langcode);
    self.name = ko.observable(langcode);
    self.default_lang = default_lang;

    self.isDefaultLang = ko.computed(function () {
        return self.langcode() === self.default_lang();
    });
    self.isNotDefaultLang = ko.computed(function () {
        return !self.isDefaultLang();
    });

    $.getJSON('/langcodes/langs.json', {term: self.langcode()}, function (res) {
        var index = _.map(res, function(r) { return r.code; }).indexOf(self.langcode());
        if (index >= 0) {
            self.name(res[index].name);
        }
    });
};
