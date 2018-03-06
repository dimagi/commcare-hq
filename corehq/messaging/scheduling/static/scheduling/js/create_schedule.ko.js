hqDefine("scheduling/js/create_schedule.ko", function() {
    var MessageViewModel = function(language_code, message) {
        var self = this;

        self.language_code = ko.observable(language_code);
        self.message = ko.observable(message);
    };

    var TranslationViewModel = function(language_codes, translations) {
        var self = this;

        if(typeof translations === 'string') {
            translations = JSON.parse(translations);
        }
        translations = translations || {};
        var initial_translate = !($.isEmptyObject(translations) || '*' in translations);

        self.translate = ko.observable(initial_translate);
        self.nonTranslatedMessage = ko.observable(translations['*']);
        self.translatedMessages = ko.observableArray();

        self.translate.subscribe(function(newValue) {
            // Automatically copy the non-translated message to any blank
            // translated messages when enabling the "translate" option
            if(newValue) {
                self.translatedMessages().forEach(function(messageModel) {
                    if(!messageModel.message()) {
                        messageModel.message(self.nonTranslatedMessage());
                    }
                });
            }
        });

        self.messagesJSONString = ko.computed(function() {
            var result = {};
            if(self.translate()) {
                self.translatedMessages().forEach(function(messageModel) {
                    result[messageModel.language_code()] = messageModel.message();
                });
            } else {
                result['*'] = self.nonTranslatedMessage();
            }
            return JSON.stringify(result);
        });

        self.loadInitialTranslatedMessages = function() {
            language_codes.forEach(function(language_code) {
                self.translatedMessages.push(new MessageViewModel(language_code, translations[language_code]));
            });
        };

        self.loadInitialTranslatedMessages();
    };

    var CreateScheduleViewModel = function (initial_values, select2_user_recipients,
        select2_user_group_recipients, select2_user_organization_recipients,
        select2_case_group_recipients, current_visit_scheduler_form) {
        var self = this;

        self.timestamp = new Date().getTime();
        self.send_frequency = ko.observable(initial_values.send_frequency);
        self.weekdays = ko.observableArray(initial_values.weekdays || []);
        self.days_of_month = ko.observableArray(initial_values.days_of_month || []);
        self.send_time = ko.observable(initial_values.send_time);
        self.send_time_type = ko.observable(initial_values.send_time_type);
        self.start_date = ko.observable(initial_values.start_date);
        self.start_date_type = ko.observable(initial_values.start_date_type);
        self.start_offset_type = ko.observable(initial_values.start_offset_type);
        self.stop_type = ko.observable(initial_values.stop_type);
        self.occurrences = ko.observable(initial_values.occurrences);
        self.recipient_types = ko.observableArray(initial_values.recipient_types || []);
        self.user_recipients = new RecipientsSelect2Handler(select2_user_recipients,
            initial_values.user_recipients, 'schedule-user_recipients');
        self.user_recipients.init();
        self.user_group_recipients = new RecipientsSelect2Handler(select2_user_group_recipients,
            initial_values.user_group_recipients, 'schedule-user_group_recipients');
        self.user_group_recipients.init();
        self.user_organization_recipients = new RecipientsSelect2Handler(select2_user_organization_recipients,
            initial_values.user_organization_recipients, 'schedule-user_organization_recipients');
        self.user_organization_recipients.init();
        self.case_group_recipients = new RecipientsSelect2Handler(select2_case_group_recipients,
            initial_values.case_group_recipients, 'schedule-case_group_recipients');
        self.case_group_recipients.init();
        self.reset_case_property_enabled = ko.observable(initial_values.reset_case_property_enabled);
        self.submit_partially_completed_forms = ko.observable(initial_values.submit_partially_completed_forms);
        self.survey_reminder_intervals_enabled = ko.observable(initial_values.survey_reminder_intervals_enabled);

        self.is_trial_project = initial_values.is_trial_project;
        self.displayed_email_trial_message = false;
        self.content = ko.observable(initial_values.content);
        self.subject = new TranslationViewModel(
            hqImport("hqwebapp/js/initial_page_data").get("language_list"),
            initial_values.subject
        );
        self.message = new TranslationViewModel(
            hqImport("hqwebapp/js/initial_page_data").get("language_list"),
            initial_values.message
        );
        self.visit_scheduler_app_and_form_unique_id = new FormSelect2Handler(current_visit_scheduler_form,
            'schedule-visit_scheduler_app_and_form_unique_id', self.timestamp);
        self.visit_scheduler_app_and_form_unique_id.init();

        self.capture_custom_metadata_item = ko.observable(initial_values.capture_custom_metadata_item);

        self.create_day_of_month_choice = function(value) {
            if(value === '-1') {
                return {code: value, name: gettext("last")};
            } else if(value === '-2') {
                return {code: value, name: gettext("last - 1")};
            } else if(value === '-3') {
                return {code: value, name: gettext("last - 2")};
            } else {
                return {code: value, name: value};
            }
        };

        self.days_of_month_choices = [
            {row: ['1', '2', '3', '4', '5', '6', '7'].map(self.create_day_of_month_choice)},
            {row: ['8', '9', '10', '11', '12', '13', '14'].map(self.create_day_of_month_choice)},
            {row: ['15', '16', '17', '18', '19', '20', '21'].map(self.create_day_of_month_choice)},
            {row: ['22', '23', '24', '25', '26', '27', '28'].map(self.create_day_of_month_choice)},
            {row: ['-3', '-2', '-1'].map(self.create_day_of_month_choice)},
        ];

        self.recipientTypeSelected = function(value) {
            return self.recipient_types().indexOf(value) !== -1;
        };

        self.toggleRecipientType = function(value) {
            if(self.recipientTypeSelected(value)) {
                self.recipient_types.remove(value);
            } else {
                self.recipient_types.push(value);
            }
        };

        self.setOccurrencesOptionText = function(newValue) {
            var occurrences = $('option[value="after_occurrences"]');
            var firstOccurrence = $('option[value="after_first_occurrence"]');
            if(newValue === 'daily') {
                occurrences.text(gettext("After occurrences:"));
                firstOccurrence.text(gettext("After first occurrence"));
            } else if(newValue === 'weekly') {
                occurrences.text(gettext("After weeks:"));
                firstOccurrence.text(gettext("After first week"));
            } else if(newValue === 'monthly') {
                occurrences.text(gettext("After months:"));
                firstOccurrence.text(gettext("After first month"));
            }
        };

        self.send_frequency.subscribe(self.setOccurrencesOptionText);

        self.showTimeInput = ko.computed(function() {
            return self.send_frequency() !== 'immediately';
        });

        self.showStartDateInput = ko.computed(function() {
            return self.send_frequency() !== 'immediately';
        });

        self.showWeekdaysInput = ko.computed(function() {
            return self.send_frequency() === 'weekly';
        });

        self.showDaysOfMonthInput = ko.computed(function() {
            return self.send_frequency() === 'monthly';
        });

        self.showStopInput = ko.computed(function() {
            return self.send_frequency() !== 'immediately';
        });

        self.computedEndDate = ko.computed(function() {
            if(self.stop_type() !== 'never') {
                var start_date_milliseconds = Date.parse(self.start_date());
                var occurrences = null;
                if(self.stop_type() === 'after_first_occurrence') {
                    occurrences = 1;
                } else {
                    occurrences = parseInt(self.occurrences());
                }

                if(!isNaN(start_date_milliseconds) && !isNaN(occurrences)) {
                    var milliseconds_in_a_day = 24 * 60 * 60 * 1000;
                    if(self.send_frequency() === 'daily') {
                        var end_date = new Date(start_date_milliseconds + ((occurrences - 1) * milliseconds_in_a_day));
                        return end_date.toJSON().substr(0, 10);
                    } else if(self.send_frequency() === 'weekly') {
                        var js_start_day_of_week = new Date(start_date_milliseconds).getUTCDay();
                        var python_start_day_of_week = (js_start_day_of_week + 6) % 7;
                        var offset_to_last_weekday_in_schedule = null;
                        for(var i = 0; i < 7; i++) {
                            var current_weekday = (python_start_day_of_week + i) % 7;
                            if(self.weekdays().indexOf(current_weekday.toString()) !== -1) {
                                offset_to_last_weekday_in_schedule = i;
                            }
                        }
                        if(offset_to_last_weekday_in_schedule !== null) {
                            var end_date = new Date(
                                start_date_milliseconds +
                                (occurrences - 1) * 7 * milliseconds_in_a_day +
                                offset_to_last_weekday_in_schedule * milliseconds_in_a_day
                            );
                            return end_date.toJSON().substr(0, 10);
                        }
                    } else if(self.send_frequency() === 'monthly') {
                        var last_day = null;
                        self.days_of_month().forEach(function(value, index) {
                            value = parseInt(value);
                            if(last_day === null) {
                                last_day = value;
                            } else if(last_day > 0) {
                                if(value < 0) {
                                    last_day = value;
                                } else if(value > last_day) {
                                    last_day = value;
                                }
                            } else {
                                if(value < 0 && value > last_day) {
                                    last_day = value;
                                }
                            }
                        });
                        if(last_day !== null) {
                            var end_date = new Date(start_date_milliseconds);
                            end_date.setUTCMonth(end_date.getUTCMonth() + occurrences - 1);
                            if(last_day < 0) {
                                end_date.setUTCMonth(end_date.getUTCMonth() + 1);
                                // Using a value of 0 sets it to the last day of the previous month
                                end_date.setUTCDate(last_day + 1);
                            } else {
                                end_date.setUTCDate(last_day);
                            }
                            return end_date.toJSON().substr(0, 10);
                        }
                    }
                }
            }
            return '';
        });

        self.initDatePicker = function(element) {
            element.datepicker({dateFormat : "yy-mm-dd"});
        };

        self.initTimePicker = function(element) {
            element.timepicker({
                showMeridian: false,
                showSeconds: false,
                defaultTime: element.val() || false,
            });
        };

        self.init = function () {
            self.initDatePicker($("#id_schedule-start_date"));
            self.initTimePicker($("#id_schedule-send_time"));
            self.setOccurrencesOptionText(self.send_frequency());
        };
    };

    var BaseSelect2Handler = hqImport("hqwebapp/js/select2_handler").BaseSelect2Handler,
        RecipientsSelect2Handler = function (initial_object_list, initial_comma_separated_list, field) {
            /*
             * initial_object_list is a list of {id: ..., text: ...} objects representing the initial value
             *
             * intial_comma_separated_list is a string representation of initial_object_list consisting of just
             * the ids separated by a comma
             */
            BaseSelect2Handler.call(this, {
                fieldName: field,
                multiple: true,
            });
            var self = this;
        
            self.getHandlerSlug = function () {
                return 'scheduling_select2_helper';
            };
        
            self.getInitialData = function () {
                return initial_object_list;
            };

            self.value(initial_comma_separated_list);
        };
    
    RecipientsSelect2Handler.prototype = Object.create(RecipientsSelect2Handler.prototype);
    RecipientsSelect2Handler.prototype.constructor = RecipientsSelect2Handler;

    var FormSelect2Handler = function (initial_object, field, timestamp) {
        /*
         * initial_object is an {id: ..., text: ...} object representing the initial value
         */
        BaseSelect2Handler.call(this, {
            fieldName: field,
            multiple: false,
        });
        var self = this;

        self.getExtraData = function() {
            return {'timestamp': timestamp};
        };

        self.getHandlerSlug = function () {
            return 'scheduling_select2_helper';
        };

        self.getInitialData = function () {
            return initial_object;
        };

        self.value(initial_object ? initial_object.id : '');
    };

    FormSelect2Handler.prototype = Object.create(FormSelect2Handler.prototype);
    FormSelect2Handler.prototype.constructor = FormSelect2Handler;

    $(function () {
        var scheduleViewModel = new CreateScheduleViewModel(
            hqImport("hqwebapp/js/initial_page_data").get("current_values"),
            hqImport("hqwebapp/js/initial_page_data").get("current_select2_user_recipients"),
            hqImport("hqwebapp/js/initial_page_data").get("current_select2_user_group_recipients"),
            hqImport("hqwebapp/js/initial_page_data").get("current_select2_user_organization_recipients"),
            hqImport("hqwebapp/js/initial_page_data").get("current_select2_case_group_recipients"),
            hqImport("hqwebapp/js/initial_page_data").get("current_visit_scheduler_form")
        );
        $('#create-schedule-form').koApplyBindings(scheduleViewModel);
        scheduleViewModel.init();
    });
});
