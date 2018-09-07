/* globals hqImport */
hqDefine("reminders/js/reminders.manage", function () {
    var manageRemindersViewModel = function (
        initial,
        choices,
        uiType,
        availableLanguages,
        initialEventTemplate
    ) {
        'use strict';
        var self = {};
    
        self.choices = choices || {};
        self.uiType = uiType;
        self.initialEventTemplate = initialEventTemplate;
    
        self.caseType = ko.observable(initial.case_type);
    
        self.defaultLang = ko.observable(initial.default_lang);
        self.availableLanguages = ko.observableArray(_.map(availableLanguages, function (langcode) {
            return reminderLanguage(langcode, self.defaultLang);
        }));
        self.showDefaultLanguageOption = ko.computed(function () {
            return self.availableLanguages().length > 1;
        });
    
        self.startReminderOn = ko.observable(initial.start_reminder_on);
        self.isStartReminderCaseProperty = ko.computed(function () {
            return self.startReminderOn() === self.choices.START_REMINDER_ON_CASE_PROPERTY;
        });
    
        self.startMatchType = ko.observable(initial.start_match_type);
        self.isStartMatchValueVisible = ko.computed(function () {
            return self.startMatchType() !== self.choices.MATCH_ANY_VALUE;
        });

        self.startPropertyOffsetType = ko.observable(initial.start_property_offset_type);
        self.startPropertyOffsetType.subscribe(function (val) {
            var initialTiming = JSON.parse(initial.event_timing);
            var allowOffsetTimingWithDate = (
                initial.start_property_offset_type === self.choices.START_REMINDER_ON_CASE_DATE &&
                initialTiming.event_interpretation === "OFFSET"
            );
            $("#id_event_timing").children("option").each(function () {
                var j = JSON.parse($(this).val());
                if (allowOffsetTimingWithDate && val === self.choices.START_REMINDER_ON_CASE_DATE &&
                   j.event_interpretation === "OFFSET") {
                    //This is here to allow editing of any old reminders that started on a date but
                    //had offset-based event interpretation. This use case is discouraged and is not
                    //supported by the new ui, but in order to allow editing of any old reminders
                    //that may use it, we have to show the offset-based event timing options when we
                    //find a reminder like this.
                    $(this).show();
                } else if (val === self.choices.START_PROPERTY_OFFSET_IMMEDIATE ||
                          val === self.choices.START_PROPERTY_OFFSET_DELAY) {
                    $(this).show();
                } else {
                    if (j.event_interpretation === "OFFSET") {
                        $(this).hide();
                    } else {
                        $(this).show();
                    }
                }
            });
        });
        self.isStartPropertyOffsetVisible = ko.computed(function () {
            return self.startPropertyOffsetType() === self.choices.START_PROPERTY_OFFSET_DELAY;
        });
    
        self.isStartDayOfWeekVisible = ko.computed(function () {
            return self.startPropertyOffsetType() === self.choices.START_REMINDER_ON_DAY_OF_WEEK;
        });
    
        self.isStartReminderCaseDate = ko.computed(function () {
            return self.startPropertyOffsetType() === self.choices.START_REMINDER_ON_CASE_DATE;
        });
    
        self.recipient = ko.observable(initial.recipient);
        self.isRecipientSubcase = ko.computed(function () {
            return self.recipient() === self.choices.RECIPIENT_SUBCASE;
        });
        self.isRecipientGroup = ko.computed(function () {
            return self.recipient() === self.choices.RECIPIENT_USER_GROUP;
        });
    
        self.recipientCaseMatchType = ko.observable(initial.recipient_case_match_type);
        self.isRecipientCaseValueVisible = ko.computed(function () {
            return self.recipientCaseMatchType() !== self.choices.MATCH_ANY_VALUE;
        });
    
        self.method = ko.observable(initial.method);
        self.eventObjects = ko.observableArray();
        self.events = ko.computed(function () {
            return JSON.stringify(_.map(self.eventObjects(), function (event) {
                return event.asJSON();
            }));
        });
        self.eventTiming = ko.observable(initial.event_timing);
        self.isEventDeleteButtonVisible = ko.computed(function () {
            return self.eventObjects().length > 1;
        });
    
        self.eventInterpretation = ko.computed(function () {
            var eventTiming = JSON.parse(self.eventTiming());
            return eventTiming.event_interpretation;
        });
    
        self.repeatType = ko.observable(initial.repeat_type);
        self.isScheduleLengthVisible = ko.computed(function () {
            return self.repeatType() !== self.choices.REPEAT_TYPE_NO;
        });
        self.isMaxIterationCountVisible = ko.computed(function () {
            return self.repeatType() === self.choices.REPEAT_TYPE_SPECIFIC;
        });
    
        self.stopCondition = ko.observable(initial.stop_condition);
        
        self.isUntilVisible = ko.computed(function () {
            return self.stopCondition() === self.choices.STOP_CONDITION_CASE_PROPERTY;
        });
    
        self.isMaxQuestionRetriesVisible = ko.computed(function () {
            return self.method() === self.choices.METHOD_IVR_SURVEY;
        });
    
        self.isForceSurveysToUsedTriggeredCaseVisible = ko.computed(function () {
            return (self.method() === self.choices.METHOD_IVR_SURVEY ||
                    self.method() === self.choices.METHOD_SMS_SURVEY);
        });
    
        self.globalTimeouts = ko.observable();
    
        self.areTimeoutsVisible = ko.computed(function () {
            return (self.method() === self.choices.METHOD_SMS_CALLBACK ||
                    self.method() === self.choices.METHOD_IVR_SURVEY ||
                    self.method() === self.choices.METHOD_SMS_SURVEY);
        });
    
        self.isGlobalTimeoutsVisible = ko.computed(function () {
            return self.areTimeoutsVisible() && self.uiType === self.choices.UI_SIMPLE_FIXED;
        });
    
        self.isOffsetTimingUsed = ko.computed(function () {
            var timing = JSON.parse(self.eventTiming());
            return timing.event_interpretation === "OFFSET";
        });
    
        self.submitPartialForms = ko.observable(initial.submit_partial_forms);
        self.isPartialSubmissionsVisible = ko.computed(function () {
            return (self.method() === self.choices.METHOD_IVR_SURVEY ||
                    self.method() === self.choices.METHOD_SMS_SURVEY);
        });
    
        self.useCustomContentHandler = ko.observable(initial.use_custom_content_handler);
        self.useCustomUserDataFilter = ko.observable(initial.use_custom_user_data_filter);
        self.customUserDataFilterField = ko.observable(initial.custom_user_data_filter_field);
        self.customUserDataFilterValue = ko.observable(initial.custom_user_data_filter_value);

        self.isTrialProject = initial.is_trial_project;
        self.displayedEmailTrialMessage = false;
        self.method.subscribe(function (newValue) {
            if (
                self.isTrialProject &&
                !self.displayedEmailTrialMessage &&
                newValue === self.choices.METHOD_EMAIL
            ) {
                $('#email-trial-message-modal').modal('show');
                self.displayedEmailTrialMessage = true;
            }
        });
    
        self.availableCaseTypes = ko.observableArray();
        self.availableCaseProperties = {};
        self.availableSubcaseProperties = {};

        self.getAvailableCaseProperties = ko.computed(function () {
            var caseType = self.caseType();
            if (self.availableCaseProperties.hasOwnProperty(caseType)) {
                return self.availableCaseProperties[caseType];
            } else {
                return [];
            }
        });

        self.getAvailableSubcaseProperties = ko.computed(function () {
            var caseType = self.caseType();
            if (self.availableSubcaseProperties.hasOwnProperty(caseType)) {
                return self.availableSubcaseProperties[caseType];
            } else {
                return [];
            }
        });
    
        self.init = function () {
            var events = JSON.parse(initial.events || '[]');
            if (self.uiType === self.choices.UI_SIMPLE_FIXED) {
                // only use the first event in the list
                events = [events[0]];
            }
            var globalTimeoutsInitial = initial.global_timeouts;
            if (globalTimeoutsInitial === null) {
                globalTimeoutsInitial = events[0].callbackTimeoutIntervals;
            }
            self.globalTimeouts(globalTimeoutsInitial);
            self.eventObjects(_.map(events, function (event) {
                return reminderEvent(
                    event,
                    self.choices,
                    self.method,
                    self.eventTiming,
                    self.eventInterpretation,
                    self.availableLanguages
                );
            }));
            self.refreshEventsListUI();
            self.initAvailableCaseTypes();
            self.initAvailableCaseProperties();
            self.initAvailableSubcaseProperties();
        };
    
        self.initAvailableCaseTypes = function () {
            $.ajax({
                type: "POST",
                dataType: "json",
                data: {
                    action: "search_case_type",
                },
            }).done(function (data, textStatus, jqXHR) {
                for (var i = 0; i < data.length; i++) {
                    self.availableCaseTypes.push(data[i]);
                }
            });
        };
    
        self.initAvailableCaseProperties = function () {
            $.ajax({
                type: "POST",
                dataType: "json",
                data: {
                    action: "search_case_property",
                },
            }).done(function (data, textStatus, jqXHR) {
                self.availableCaseProperties = data;
            });
        };
    
        self.initAvailableSubcaseProperties = function () {
            $.ajax({
                type: "POST",
                dataType: "json",
                data: {
                    action: "search_subcase_property",
                },
            }).done(function (data, textStatus, jqXHR) {
                self.availableSubcaseProperties = data;
            });
        };
    
        self.addEvent = function () {
            var newEventTemplate = self.initialEventTemplate;
            _(self.availableLanguages()).each(function (language) {
                newEventTemplate.message[language.langcode()] = "";
            });
            self.eventObjects.push(reminderEvent(
                newEventTemplate,
                self.choices,
                self.method,
                self.eventTiming,
                self.eventInterpretation,
                self.availableLanguages
            ));
        };
    
        self.removeEvent = function (event) {
            self.eventObjects.remove(event);
            self.refreshEventsListUI();
        };
    
        self.refreshEventsListUI = function () {
            $('.hq-help-template').each(function () {
                hqImport("hqwebapp/js/main").transformHelpTemplate($(this), true);
            });
            $('[data-timeset="true"]').each(function () {
                $(this).timepicker({
                    showMeridian: false,
                    showSeconds: true,
                    defaultTime: $(this).val() || false,
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
                            term: term,
                        };
                    },
                    results: function (data) {
                        return {
                            results: data,
                        };
                    },
                },
                initSelection: function (element, callback) {
                    if (element.val()) {
                        try {
                            $.ajax({
                                type: "POST",
                                dataType: "json",
                                data: {
                                    action: "search_form_by_id",
                                    term: element.val(),
                                },
                            }).done(function (data, textStatus, jqXHR) {
                                if (data.id && data.text) {
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
                },
            });
        };

        return self;
    };
    
    var reminderEvent = function (
        eventData,
        choices,
        method,
        eventTiming,
        eventInterpretation,
        availableLanguages
    ) {
        'use strict';
        var self = {};
        self.choices = choices;
        self.method = method;
        self.eventTiming = eventTiming;
        self.eventInterpretation = eventInterpretation;
        self.availableLanguages = availableLanguages;
    
        self.fireTimeType = ko.computed(function () {
            var eventTiming = JSON.parse(self.eventTiming());
            return eventTiming.fire_time_type;
        });
    
        self.isEventImmediate = ko.computed(function () {
            var eventTiming = JSON.parse(self.eventTiming());
            return eventTiming.special === self.choices.EVENT_TIMING_IMMEDIATE;
        });
    
        self.dayNum = ko.observable(eventData.day_num);
    
        self.fireTime = ko.observable(eventData.fire_time);
        self.isFireTimeVisible = ko.computed(function () {
            return ((self.fireTimeType() === self.choices.FIRE_TIME_DEFAULT) && !self.isEventImmediate())
                || self.fireTimeType() === self.choices.FIRE_TIME_RANDOM;
        });
    
        self.fireTimeAux = ko.observable(eventData.fire_time_aux);
        self.isFireTimeAuxVisible = ko.computed(function () {
            return self.fireTimeType() === self.choices.FIRE_TIME_CASE_PROPERTY;
        });
    
        self.timeWindowLength = ko.observable(eventData.time_window_length || "");
        self.isWindowLengthVisible = ko.computed(function () {
            return self.fireTimeType() === self.choices.FIRE_TIME_RANDOM;
        });
    
        self.formUniqueId = ko.observable(eventData.form_unique_id);
        self.isSurveyVisible = ko.computed(function () {
            return (self.method() === self.choices.METHOD_SMS_SURVEY)
                || (self.method() === self.choices.METHOD_IVR_SURVEY);
        });
    
        var initialMessagesArray = [];
        for (var langcode in eventData.message) {
            initialMessagesArray.push(
                reminderMessage(
                    eventData.subject[langcode],
                    eventData.message[langcode],
                    langcode,
                    self.availableLanguages
                )
            );
        }
        self.messageTranslations = ko.observableArray(initialMessagesArray);
    
        self.callbackTimeoutIntervals = ko.observable(eventData.callback_timeout_intervals);
    
        self.subjectData = ko.computed(function () {
            var subjectData = {};
            _.each(self.messageTranslations(), function (translation) {
                subjectData[translation.langcode()] = translation.subject();
            });
            return subjectData;
        });
    
        self.messageData = ko.computed(function () {
            var messageData = {};
            _.each(self.messageTranslations(), function (translation) {
                messageData[translation.langcode()] = translation.message();
            });
            return messageData;
        });
    
        self.isEmailSelected = ko.computed(function () {
            return self.method() === self.choices.METHOD_EMAIL;
        });
    
        self.isSubjectVisible = ko.computed(function () {
            return self.isEmailSelected();
        });
    
        self.isMessageVisible = ko.computed(function () {
            return (self.method() === self.choices.METHOD_SMS) ||
                   (self.method() === self.choices.METHOD_SMS_CALLBACK) ||
                   self.isEmailSelected();
        });
    
        self.asJSON = ko.computed(function () {
            return {
                fire_time_type: self.fireTimeType(),
                fire_time_aux: self.fireTimeAux(),
                is_immediate: self.isEventImmediate(),
                day_num: self.dayNum(),
                fire_time: self.fireTime(),
                form_unique_id: self.formUniqueId(),
                subject: self.subjectData(),
                message: self.messageData(),
                callback_timeout_intervals: self.callbackTimeoutIntervals(),
                time_window_length: self.timeWindowLength(),
            };
        });

        return self;
    };
    
    var reminderMessage = function (subject, message, langcode, availableLanguages) {
        'use strict';
        var self = {};
        self.langcode = ko.observable(langcode);
        self.subject = ko.observable(subject);
        self.message = ko.observable(message);
        self.availableLanguages = availableLanguages;
    
        self.messageLength = ko.computed(function () {
            return self.message().length;
        });
        self.totalMessages = ko.computed(function () {
            return Math.ceil(self.messageLength() / 160);
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
            if (self.availableLanguages().length === 1) {
                return "";
            }
            var languageName = self.langcode();
            _.each(self.availableLanguages(), function (lang) {
                if (lang.langcode() === self.langcode()) {
                    languageName = lang.name();
                }
            });
            return languageName;
        });
        return self;
    };
    
    var reminderLanguage = function (langcode, defaultLang) {
        'use strict';
        var self = {};
    
        self.langcode = ko.observable(langcode);
        self.name = ko.observable(langcode);
        self.defaultLang = defaultLang;
    
        self.isDefaultLang = ko.computed(function () {
            return self.langcode() === self.defaultLang();
        });
        self.isNotDefaultLang = ko.computed(function () {
            return !self.isDefaultLang();
        });
    
        $.getJSON('/langcodes/langs.json', {term: self.langcode()}, function (res) {
            var index = _.map(res, function (r) { return r.code; }).indexOf(self.langcode());
            if (index >= 0) {
                self.name(res[index].name);
            }
        });

        return self;
    };

    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
            manageRemindersModel = manageRemindersViewModel(
                initial_page_data("current_values"),
                initial_page_data("relevant_choices"),
                initial_page_data("ui_type"),
                initial_page_data("available_languages"),
                initial_page_data("initial_event")
            );
        $('#manage-reminders-form').koApplyBindings(manageRemindersModel);
        manageRemindersModel.init();
    });
});
