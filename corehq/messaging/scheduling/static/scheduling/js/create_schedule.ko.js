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
        self.repeat = ko.observable(initial_values.repeat);
        self.repeat_every = ko.observable(initial_values.repeat_every);
        self.stop_type = ko.observable(initial_values.stop_type);
        self.occurrences = ko.observable(initial_values.occurrences);
        self.recipient_types = ko.observableArray(initial_values.recipient_types || []);
        self.user_recipients = new recipientsSelect2Handler(select2_user_recipients,
            initial_values.user_recipients, 'schedule-user_recipients');
        self.user_recipients.init();
        self.user_group_recipients = new recipientsSelect2Handler(select2_user_group_recipients,
            initial_values.user_group_recipients, 'schedule-user_group_recipients');
        self.user_group_recipients.init();
        self.user_organization_recipients = new recipientsSelect2Handler(select2_user_organization_recipients,
            initial_values.user_organization_recipients, 'schedule-user_organization_recipients');
        self.user_organization_recipients.init();
        self.case_group_recipients = new recipientsSelect2Handler(select2_case_group_recipients,
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
        self.visit_scheduler_app_and_form_unique_id = new formSelect2Handler(current_visit_scheduler_form,
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

        self.setRepeatOptionText = function(newValue) {
            var option = $('option[value="repeat_every_1"]');
            if(newValue === 'daily') {
                option.text(gettext("every day"));
            } else if(newValue === 'weekly') {
                option.text(gettext("every week"));
            } else if(newValue === 'monthly') {
                option.text(gettext("every month"));
            }
        };

        self.send_frequency.subscribe(self.setRepeatOptionText);

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

        self.showRepeatInput = ko.computed(function() {
            return self.send_frequency() !== 'immediately';
        });

        self.calculateDailyEndDate = function(start_date_milliseconds, repeat_every, occurrences) {
            var milliseconds_in_a_day = 24 * 60 * 60 * 1000;
            var days_until_end_date = (occurrences - 1) * repeat_every;
            return new Date(start_date_milliseconds + (days_until_end_date * milliseconds_in_a_day));
        };

        self.calculateWeeklyEndDate = function(start_date_milliseconds, repeat_every, occurrences) {
            var milliseconds_in_a_day = 24 * 60 * 60 * 1000;
            var js_start_day_of_week = new Date(start_date_milliseconds).getUTCDay();
            var python_start_day_of_week = (js_start_day_of_week + 6) % 7;
            var offset_to_last_weekday_in_schedule = null;
            for(var i = 0; i < 7; i++) {
                var current_weekday = (python_start_day_of_week + i) % 7;
                if(self.weekdays().indexOf(current_weekday.toString()) !== -1) {
                    offset_to_last_weekday_in_schedule = i;
                }
            }
            if(offset_to_last_weekday_in_schedule === null) {
                return null;
            }

            return new Date(
                start_date_milliseconds +
                offset_to_last_weekday_in_schedule * milliseconds_in_a_day +
                (occurrences - 1) * 7 * repeat_every * milliseconds_in_a_day
            );
        };

        self.calculateMonthlyEndDate = function(start_date_milliseconds, repeat_every, occurrences) {
            var last_day = null;
            self.days_of_month().forEach(function(value) {
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
            if(last_day === null) {
                return null;
            }

            var end_date = new Date(start_date_milliseconds);
            end_date.setUTCMonth(end_date.getUTCMonth() + (occurrences - 1) * repeat_every);
            if(last_day < 0) {
                end_date.setUTCMonth(end_date.getUTCMonth() + 1);
                // Using a value of 0 sets it to the last day of the previous month
                end_date.setUTCDate(last_day + 1);
            } else {
                end_date.setUTCDate(last_day);
            }
            return end_date;
        };

        self.calculateOccurrences = function() {
            if(self.repeat() === 'no') {
                return 1;
            } else if(self.stop_type() === 'never') {
                return NaN;
            } else {
                var value = parseInt(self.occurrences());
                if(value <= 0) {
                    return NaN;
                }
                return value;
            }
        };

        self.calculateRepeatEvery = function() {
            if(self.repeat() === 'repeat_every_n') {
                var value = parseInt(self.repeat_every());
                if(value <= 0) {
                    return NaN;
                }
                return value;
            } else {
                return 1;
            }
        };

        self.computedEndDate = ko.computed(function() {
            var start_date_milliseconds = Date.parse(self.start_date());
            var repeat_every = self.calculateRepeatEvery();
            var occurrences = self.calculateOccurrences();

            if(self.start_date_type() && self.start_date_type() !== 'SPECIFIC_DATE') {
                return '';
            }

            if(isNaN(start_date_milliseconds) || isNaN(occurrences) || isNaN(repeat_every)) {
                return '';
            }

            var end_date = null;
            if(self.send_frequency() === 'daily') {
                end_date = self.calculateDailyEndDate(start_date_milliseconds, repeat_every, occurrences);
            } else if(self.send_frequency() === 'weekly') {
                end_date = self.calculateWeeklyEndDate(start_date_milliseconds, repeat_every, occurrences);
            } else if(self.send_frequency() === 'monthly') {
                end_date = self.calculateMonthlyEndDate(start_date_milliseconds, repeat_every, occurrences);
            }

            if(end_date) {
                return end_date.toJSON().substr(0, 10);
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
            self.setRepeatOptionText(self.send_frequency());
        };
    };

    var baseSelect2Handler = hqImport("hqwebapp/js/select2_handler").baseSelect2Handler,
        recipientsSelect2Handler = function (initial_object_list, initial_comma_separated_list, field) {
            /*
             * initial_object_list is a list of {id: ..., text: ...} objects representing the initial value
             *
             * intial_comma_separated_list is a string representation of initial_object_list consisting of just
             * the ids separated by a comma
             */
            var self = baseSelect2Handler({
                fieldName: field,
                multiple: true,
            });
        
            self.getHandlerSlug = function () {
                return 'scheduling_select2_helper';
            };
        
            self.getInitialData = function () {
                return initial_object_list;
            };

            self.value(initial_comma_separated_list);

            return self;
        };
    
    recipientsSelect2Handler.prototype = Object.create(recipientsSelect2Handler.prototype);
    recipientsSelect2Handler.prototype.constructor = recipientsSelect2Handler;

    var formSelect2Handler = function (initial_object, field, timestamp) {
        /*
         * initial_object is an {id: ..., text: ...} object representing the initial value
         */
        var self = baseSelect2Handler({
            fieldName: field,
            multiple: false,
        });

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

        return self;
    };

    formSelect2Handler.prototype = Object.create(formSelect2Handler.prototype);
    formSelect2Handler.prototype.constructor = formSelect2Handler;

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
