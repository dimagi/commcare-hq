var ManageRemindersViewModel = function (
    initial,
    choices,
    ui_type,
    available_languages,
    initial_event_template
) {
    'use strict';
    var self = this;

    self.choices = choices || {};
    self.ui_type = ui_type;
    self.initial_event_template = initial_event_template;

    self.case_type = ko.observable(initial.case_type);

    self.default_lang = ko.observable(initial.default_lang);
    self.available_languages = ko.observableArray(_.map(available_languages, function (langcode) {
        return new ReminderLanguage(langcode, self.default_lang);
    }));
    self.showDefaultLanguageOption = ko.computed(function () {
        return self.available_languages().length > 1;
    });

    self.start_reminder_on = ko.observable(initial.start_reminder_on);
    self.isStartReminderCaseProperty = ko.computed(function () {
        return self.start_reminder_on() === self.choices.START_REMINDER_ON_CASE_PROPERTY;
    });

    self.start_match_type = ko.observable(initial.start_match_type);
    self.isStartMatchValueVisible = ko.computed(function () {
        return self.start_match_type() !== self.choices.MATCH_ANY_VALUE;
    });

    self.start_property_offset_type = ko.observable(initial.start_property_offset_type);
    self.start_property_offset_type.subscribe(function(val) {
        var initial_timing = JSON.parse(initial.event_timing);
        var allow_offset_timing_with_date = (
            initial.start_property_offset_type === self.choices.START_REMINDER_ON_CASE_DATE &&
            initial_timing.event_interpretation === "OFFSET"
        );
        $("#id_event_timing").children("option").each(function(i) {
            var j = JSON.parse($(this).val());
            if(allow_offset_timing_with_date && val === self.choices.START_REMINDER_ON_CASE_DATE &&
               j.event_interpretation === "OFFSET") {
                //This is here to allow editing of any old reminders that started on a date but
                //had offset-based event interpretation. This use case is discouraged and is not
                //supported by the new ui, but in order to allow editing of any old reminders
                //that may use it, we have to show the offset-based event timing options when we
                //find a reminder like this.
                $(this).show();
            } else if(val === self.choices.START_PROPERTY_OFFSET_IMMEDIATE ||
                      val === self.choices.START_PROPERTY_OFFSET_DELAY) {
                $(this).show();
            } else {
                if(j.event_interpretation === "OFFSET") {
                    $(this).hide();
                } else {
                    $(this).show()
                }
            }
        });
    });
    self.isStartPropertyOffsetVisible = ko.computed(function () {
        return self.start_property_offset_type() === self.choices.START_PROPERTY_OFFSET_DELAY;
    });

    self.isStartDayOfWeekVisible = ko.computed(function () {
        return self.start_property_offset_type() === self.choices.START_REMINDER_ON_DAY_OF_WEEK;
    });

    self.isStartReminderCaseDate = ko.computed(function () {
        return self.start_property_offset_type() === self.choices.START_REMINDER_ON_CASE_DATE;
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
        var event_timing = JSON.parse(self.event_timing());
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

    self.areTimeoutsVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_SMS_CALLBACK ||
                self.method() === self.choices.METHOD_IVR_SURVEY ||
                self.method() === self.choices.METHOD_SMS_SURVEY);
    });

    self.isGlobalTimeoutsVisible = ko.computed(function () {
        return self.areTimeoutsVisible() && self.ui_type === self.choices.UI_SIMPLE_FIXED;
    });

    self.isOffsetTimingUsed = ko.computed(function () {
        var timing = JSON.parse(self.event_timing());
        return timing.event_interpretation === "OFFSET";
    });

    self.submit_partial_forms = ko.observable(initial.submit_partial_forms);
    self.isPartialSubmissionsVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_IVR_SURVEY ||
                self.method() === self.choices.METHOD_SMS_SURVEY);
    });

    self.use_custom_content_handler = ko.observable(initial.use_custom_content_handler);

    self.is_trial_project = initial.is_trial_project;
    self.displayed_email_trial_message = false;
    self.method.subscribe(function(newValue) {
        if(
            self.is_trial_project &&
            !self.displayed_email_trial_message &&
            newValue === self.choices.METHOD_EMAIL
        ) {
            $('#email-trial-message-modal').modal('show');
            self.displayed_email_trial_message = true;
        }
    });

    self.available_case_types = ko.observableArray();
    self.available_case_properties = {};
    self.available_subcase_properties = {};

    self.getAvailableCaseProperties = ko.computed(function() {
        var case_type = self.case_type();
        if(self.available_case_properties.hasOwnProperty(case_type)) {
            return self.available_case_properties[case_type];
        } else {
            return [];
        }
    });

    self.getAvailableSubcaseProperties = ko.computed(function() {
        var case_type = self.case_type();
        if(self.available_subcase_properties.hasOwnProperty(case_type)) {
            return self.available_subcase_properties[case_type];
        } else {
            return [];
        }
    });

    self.init = function () {
        var events = JSON.parse(initial.events || '[]');
        if (self.ui_type === self.choices.UI_SIMPLE_FIXED) {
            // only use the first event in the list
            events = [events[0]];
        }
        var global_timeouts_initial = initial.global_timeouts;
        if (global_timeouts_initial === null) {
            global_timeouts_initial = events[0].callback_timeout_intervals;
        }
        self.global_timeouts(global_timeouts_initial);
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
        self.initAvailableCaseTypes();
        self.initAvailableCaseProperties();
        self.initAvailableSubcaseProperties();
    };

    self.initAvailableCaseTypes = function() {
        $.ajax({
            type: "POST",
            dataType: "json",
            data: {
                action: "search_case_type",
            }
        }).done(function(data, textStatus, jqXHR) {
            for(var i = 0; i < data.length; i++) {
                self.available_case_types.push(data[i]);
            }
        });
    };

    self.initAvailableCaseProperties = function() {
        $.ajax({
            type: "POST",
            dataType: "json",
            data: {
                action: "search_case_property",
            }
        }).done(function(data, textStatus, jqXHR) {
            self.available_case_properties = data;
        });
    };

    self.initAvailableSubcaseProperties = function() {
        $.ajax({
            type: "POST",
            dataType: "json",
            data: {
                action: "search_subcase_property",
            }
        }).done(function(data, textStatus, jqXHR) {
            self.available_subcase_properties = data;
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
        $('.hq-help-template').each(function () {
            COMMCAREHQ.transformHelpTemplate($(this), true);
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
                        $.ajax({
                            type: "POST",
                            dataType: "json",
                            data: {
                                action: "search_form_by_id",
                                term: element.val()
                            }
                        }).done(function(data, textStatus, jqXHR) {
                            if(data.id && data.text) {
                                callback(data);
                            }
                        });
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
        var event_timing = JSON.parse(self.event_timing());
        return event_timing.fire_time_type;
    });

    self.isEventImmediate = ko.computed(function () {
        var event_timing = JSON.parse(self.event_timing());
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

    var initialMessagesArray = [];
    for(var langcode in eventData.message) {
        initialMessagesArray.push(
            new ReminderMessage(
                eventData.subject[langcode],
                eventData.message[langcode],
                langcode,
                self.available_languages
            )
        );
    }
    self.messageTranslations = ko.observableArray(initialMessagesArray);

    self.callback_timeout_intervals = ko.observable(eventData.callback_timeout_intervals);

    self.subject_data = ko.computed(function () {
        var subject_data = {};
        _.each(self.messageTranslations(), function (translation) {
            subject_data[translation.langcode()] = translation.subject();
        });
        return subject_data;
    });

    self.message_data = ko.computed(function () {
        var message_data = {};
        _.each(self.messageTranslations(), function (translation) {
            message_data[translation.langcode()] = translation.message();
        });
        return message_data;
    });

    self.isEmailSelected = ko.computed(function() {
        return self.method() === self.choices.METHOD_EMAIL;
    });

    self.isSubjectVisible = ko.computed(function() {
        return self.isEmailSelected();
    });

    self.isMessageVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_SMS) ||
               (self.method() === self.choices.METHOD_SMS_CALLBACK) ||
               self.isEmailSelected();
    });

    self.asJSON = ko.computed(function () {
        return {
            fire_time_type: self.fire_time_type(),
            fire_time_aux: self.fire_time_aux(),
            is_immediate: self.isEventImmediate(),
            day_num: self.day_num(),
            fire_time: self.fire_time(),
            form_unique_id: self.form_unique_id(),
            subject: self.subject_data(),
            message: self.message_data(),
            callback_timeout_intervals: self.callback_timeout_intervals(),
            time_window_length: self.time_window_length()
        }
    });
};

var ReminderMessage = function (subject, message, langcode, available_languages) {
    'use strict';
    var self = this;
    self.langcode = ko.observable(langcode);
    self.subject = ko.observable(subject);
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
