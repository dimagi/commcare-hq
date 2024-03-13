hqDefine("scheduling/js/create_schedule.ko", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/select2_handler',
    'jquery-ui/ui/widgets/datepicker',
    'bootstrap-timepicker/js/bootstrap-timepicker',
    'hqwebapp/js/ckeditor_knockout_bindings',
], function ($, ko, initialPageData, select2Handler) {
    ko.bindingHandlers.useTimePicker = {
        init: function (element, valueAccessor, allBindings, viewModel, bindingContext) {
            $(element).timepicker({
                showMeridian: false,
                showSeconds: false,
                defaultTime: $(element).val() || '',
            });
        },
        update: function (element, valueAccessor, allBindings, viewModel, bindingContext) {},
    };

    var MessageViewModel = function (language_code, message) {
        var self = this;

        self.language_code = ko.observable(language_code);
        self.message = ko.observable(message);
        self.html_message = ko.observable(message);
    };

    var TranslationViewModel = function (language_codes, translations) {
        var self = this;

        if (typeof translations === 'string') {
            translations = JSON.parse(translations);
        }
        translations = translations || {};
        var initial_translate = !($.isEmptyObject(translations) || '*' in translations);

        self.translate = ko.observable(initial_translate);
        self.nonTranslatedMessage = ko.observable(translations['*']);
        self.translatedMessages = ko.observableArray();

        self.translate.subscribe(function (newValue) {
            // Automatically copy the non-translated message to any blank
            // translated messages when enabling the "translate" option
            if (newValue) {
                self.translatedMessages().forEach(function (messageModel) {
                    if (!messageModel.message()) {
                        messageModel.message(self.nonTranslatedMessage());
                    }
                    if (!messageModel.html_message()) {
                        messageModel.html_message(self.nonTranslatedMessage());
                    }
                });
            }
        });

        self.messagesJSONString = ko.computed(function () {
            var result = {};
            if (self.translate()) {
                self.translatedMessages().forEach(function (messageModel) {
                    result[messageModel.language_code()] = messageModel.message();
                });
            } else {
                result['*'] = self.nonTranslatedMessage();
            }
            return JSON.stringify(result);
        });

        self.htmlMessagesJSONString = ko.computed(function () {
            var result = {};
            if (self.translate()) {
                self.translatedMessages().forEach(function (messageModel) {
                    result[messageModel.language_code()] = messageModel.html_message();
                });
            } else {
                result['*'] = self.nonTranslatedMessage();
            }
            return JSON.stringify(result);
        });

        self.loadInitialTranslatedMessages = function () {
            language_codes.forEach(function (language_code) {
                self.translatedMessages.push(new MessageViewModel(language_code, translations[language_code]));
            });
        };

        self.loadInitialTranslatedMessages();
    };

    var ContentViewModel = function (initial_values) {
        var self = this;

        self.subject = new TranslationViewModel(
            initialPageData.get("language_list"),
            initial_values.subject
        );

        self.message = new TranslationViewModel(
            initialPageData.get("language_list"),
            initial_values.message
        );
        self.html_message = new TranslationViewModel(
            initialPageData.get("language_list"),
            initial_values.html_message
        );

        self.survey_reminder_intervals_enabled = ko.observable(initial_values.survey_reminder_intervals_enabled);
        self.fcm_message_type = ko.observable(initial_values.fcm_message_type);

    };

    var EventAndContentViewModel = function (initial_values) {
        var self = this;
        ContentViewModel.call(self, initial_values);

        self.day = ko.observable(initial_values.day);
        self.time = ko.observable(initial_values.time);
        self.case_property_name = ko.observable(initial_values.case_property_name);
        self.minutes_to_wait = ko.observable(initial_values.minutes_to_wait);
        self.deleted = ko.observable(initial_values.DELETE);
        self.order = ko.observable(initial_values.ORDER);

        self.waitTimeDisplay = ko.computed(function () {
            var minutes_to_wait = parseInt(self.minutes_to_wait());
            if (minutes_to_wait >= 0) {
                var hours = Math.floor(minutes_to_wait / 60);
                var minutes = minutes_to_wait % 60;
                var hours_text = hours + ' ' + gettext('hour(s)');
                var minutes_text = minutes + ' ' + gettext('minute(s)');
                if (hours > 0) {
                    return hours_text + ', ' + minutes_text;
                } else {
                    return minutes_text;
                }
            }
            return '';
        });
    };

    EventAndContentViewModel.prototype = Object.create(EventAndContentViewModel.prototype);
    EventAndContentViewModel.prototype.constructor = EventAndContentViewModel;

    var CustomEventContainer = function (id) {
        var self = this;
        var initialCustomEventValue;
        self.event_id = id;

        var customEventFormset = initialPageData.get("current_values").custom_event_formset;


        if (id < customEventFormset.length) {
            initialCustomEventValue = customEventFormset[id];
        } else {
            initialCustomEventValue = {
                day: 1,
                time: '12:00',
                minutes_to_wait: 0,
                deleted: false,
                html_message: { '*': initialPageData.get('html_message_template') },
            };
        }

        self.eventAndContentViewModel = Object.create(EventAndContentViewModel.prototype);
        self.eventAndContentViewModel.constructor(initialCustomEventValue);

        self.templateId = ko.computed(function () {
            return 'id_custom_event_template_' + id;
        });
    };

    var CreateScheduleViewModel = function (initial_values, select2_user_recipients,
        select2_user_group_recipients, select2_user_organization_recipients, select2_location_types,
        select2_case_group_recipients, current_visit_scheduler_form) {
        var self = this;

        self.useCase = ko.observable(initial_values.use_case);
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
        $('#id_schedule-recipient_types').select2();

        self.user_recipients = new recipientsSelect2Handler(select2_user_recipients,
            initial_values.user_recipients, 'schedule-user_recipients');
        self.user_recipients.init();

        self.user_group_recipients = new recipientsSelect2Handler(select2_user_group_recipients,
            initial_values.user_group_recipients, 'schedule-user_group_recipients');
        self.user_group_recipients.init();

        self.user_organization_recipients = new recipientsSelect2Handler(select2_user_organization_recipients,
            initial_values.user_organization_recipients, 'schedule-user_organization_recipients');
        self.user_organization_recipients.init();

        self.include_descendant_locations = ko.observable(initial_values.include_descendant_locations);
        self.restrict_location_types = ko.observable(initial_values.restrict_location_types);

        self.location_types = new recipientsSelect2Handler(select2_location_types,
            initial_values.location_types, 'schedule-location_types');
        self.location_types.init();

        self.case_group_recipients = new recipientsSelect2Handler(select2_case_group_recipients,
            initial_values.case_group_recipients, 'schedule-case_group_recipients');
        self.case_group_recipients.init();

        self.reset_case_property_enabled = ko.observable(initial_values.reset_case_property_enabled);
        self.stop_date_case_property_enabled = ko.observable(initial_values.stop_date_case_property_enabled);
        self.submit_partially_completed_forms = ko.observable(initial_values.submit_partially_completed_forms);

        self.is_trial_project = initial_values.is_trial_project;
        self.displayed_email_trial_message = false;
        self.content = ko.observable(initial_values.content);
        self.standalone_content_form = new ContentViewModel(initial_values.standalone_content_form);
        self.custom_events = ko.observableArray();
        self.visit_scheduler_app_and_form_unique_id = new formSelect2Handler(current_visit_scheduler_form,
            'schedule-visit_scheduler_app_and_form_unique_id', self.timestamp);
        self.visit_scheduler_app_and_form_unique_id.init();

        self.use_user_data_filter = ko.observable(initial_values.use_user_data_filter);
        self.capture_custom_metadata_item = ko.observable(initial_values.capture_custom_metadata_item);
        self.editing_custom_immediate_schedule = ko.observable(initial_values.editing_custom_immediate_schedule);

        self.create_day_of_month_choice = function (value) {
            if (value === '-1') {
                return {code: value, name: gettext("last")};
            } else if (value === '-2') {
                return {code: value, name: gettext("last - 1")};
            } else if (value === '-3') {
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

        self.recipientTypeSelected = function (value) {
            return self.recipient_types().indexOf(value) !== -1;
        };

        self.setRepeatOptionText = function (newValue) {
            var option = $('option[value="repeat_every_1"]');
            if (newValue === 'daily' || newValue === 'custom_daily') {
                option.text(gettext("every day"));
            } else if (newValue === 'weekly') {
                option.text(gettext("every week"));
            } else if (newValue === 'monthly') {
                option.text(gettext("every month"));
            }
        };

        self.send_frequency.subscribe(self.setRepeatOptionText);

        self.usesCustomEventDefinitions = ko.computed(function () {
            return self.send_frequency() === 'custom_daily' || self.send_frequency() === 'custom_immediate';
        });

        self.showSharedTimeInput = ko.computed(function () {
            return $.inArray(self.send_frequency(), ['daily', 'weekly', 'monthly']) !== -1;
        });

        self.showWeekdaysInput = ko.computed(function () {
            return self.send_frequency() === 'weekly';
        });

        self.showDaysOfMonthInput = ko.computed(function () {
            return self.send_frequency() === 'monthly';
        });

        self.usesTimedSchedule = ko.computed(function () {
            return $.inArray(self.send_frequency(), ['daily', 'weekly', 'monthly', 'custom_daily']) !== -1;
        });

        self.calculateDailyEndDate = function (start_date_milliseconds, repeat_every, occurrences) {
            var milliseconds_in_a_day = 24 * 60 * 60 * 1000;
            var days_until_end_date = (occurrences - 1) * repeat_every;
            return new Date(start_date_milliseconds + (days_until_end_date * milliseconds_in_a_day));
        };

        self.calculateWeeklyEndDate = function (start_date_milliseconds, repeat_every, occurrences) {
            var milliseconds_in_a_day = 24 * 60 * 60 * 1000;
            var js_start_day_of_week = new Date(start_date_milliseconds).getUTCDay();
            var python_start_day_of_week = (js_start_day_of_week + 6) % 7;
            var offset_to_last_weekday_in_schedule = null;
            for (var i = 0; i < 7; i++) {
                var current_weekday = (python_start_day_of_week + i) % 7;
                if (self.weekdays().indexOf(current_weekday.toString()) !== -1) {
                    offset_to_last_weekday_in_schedule = i;
                }
            }
            if (offset_to_last_weekday_in_schedule === null) {
                return null;
            }

            return new Date(
                start_date_milliseconds +
                offset_to_last_weekday_in_schedule * milliseconds_in_a_day +
                (occurrences - 1) * 7 * repeat_every * milliseconds_in_a_day
            );
        };

        self.calculateMonthlyEndDate = function (start_date_milliseconds, repeat_every, occurrences) {
            var last_day = null;
            self.days_of_month().forEach(function (value) {
                value = parseInt(value);
                if (last_day === null) {
                    last_day = value;
                } else if (last_day > 0) {
                    if (value < 0) {
                        last_day = value;
                    } else if (value > last_day) {
                        last_day = value;
                    }
                } else {
                    if (value < 0 && value > last_day) {
                        last_day = value;
                    }
                }
            });
            if (last_day === null) {
                return null;
            }

            var end_date = new Date(start_date_milliseconds);
            end_date.setUTCMonth(end_date.getUTCMonth() + (occurrences - 1) * repeat_every);
            if (last_day < 0) {
                end_date.setUTCMonth(end_date.getUTCMonth() + 1);
                // Using a value of 0 sets it to the last day of the previous month
                end_date.setUTCDate(last_day + 1);
            } else {
                end_date.setUTCDate(last_day);
            }
            return end_date;
        };

        self.calculateOccurrences = function () {
            if (self.repeat() === 'no') {
                return 1;
            } else if (self.stop_type() === 'never') {
                return NaN;
            } else {
                var value = parseInt(self.occurrences());
                if (value <= 0) {
                    return NaN;
                }
                return value;
            }
        };

        self.calculateRepeatEvery = function () {
            if (self.repeat() === 'repeat_every_n') {
                var value = parseInt(self.repeat_every());
                if (value <= 0) {
                    return NaN;
                }
                return value;
            } else {
                return 1;
            }
        };

        self.computedEndDate = ko.computed(function () {
            var start_date_milliseconds = Date.parse(self.start_date());
            var repeat_every = self.calculateRepeatEvery();
            var occurrences = self.calculateOccurrences();

            if (self.start_date_type() && self.start_date_type() !== 'SPECIFIC_DATE') {
                return '';
            }

            if (isNaN(start_date_milliseconds) || isNaN(occurrences) || isNaN(repeat_every)) {
                return '';
            }

            var end_date = null;
            if (self.send_frequency() === 'daily') {
                end_date = self.calculateDailyEndDate(start_date_milliseconds, repeat_every, occurrences);
            } else if (self.send_frequency() === 'weekly') {
                end_date = self.calculateWeeklyEndDate(start_date_milliseconds, repeat_every, occurrences);
            } else if (self.send_frequency() === 'monthly') {
                end_date = self.calculateMonthlyEndDate(start_date_milliseconds, repeat_every, occurrences);
            }

            if (end_date) {
                return end_date.toJSON().substr(0, 10);
            }

            return '';
        });

        self.saveBroadcastText = ko.computed(function () {
            if (self.send_frequency() === 'immediately') {
                return gettext("Send Broadcast");
            } else {
                return gettext("Schedule Broadcast");
            }
        });

        self.initDatePicker = function (element) {
            element.datepicker({dateFormat: "yy-mm-dd"});
        };

        self.getNextCustomEventIndex = function () {
            var count = $('#id_custom-event-TOTAL_FORMS').val();
            return parseInt(count);
        };

        self.addCustomEvent = function () {
            var id = self.getNextCustomEventIndex();
            $('#id_custom_event_templates').append(
                $('#id_custom_event_empty_form_container').html().replace(/__prefix__/g, id)
            );
            $('#id_custom-event-TOTAL_FORMS').val(id + 1);
            self.custom_events.push(new CustomEventContainer(id));
        };

        self.markCustomEventDeleted = function (event_id) {
            $.each(self.custom_events(), function (index, value) {
                if (value.event_id === event_id) {
                    value.eventAndContentViewModel.deleted(true);
                }
            });
        };

        self.getCustomEventIndex = function (event_id, arr) {
            var item_index = null;
            $.each(arr, function (index, value) {
                if (value.event_id === event_id) {
                    item_index = index;
                }
            });
            return item_index;
        };

        self.moveCustomEventUp = function (event_id) {
            var new_array = self.custom_events();
            var item_index = self.getCustomEventIndex(event_id, new_array);
            var swapped_item = null;

            while (item_index > 0 && (swapped_item === null || swapped_item.eventAndContentViewModel.deleted())) {
                swapped_item = new_array[item_index - 1];
                new_array[item_index - 1] = new_array[item_index];
                new_array[item_index] = swapped_item;
                item_index -= 1;
            }

            self.custom_events(new_array);
        };

        self.moveCustomEventDown = function (event_id) {
            var new_array = self.custom_events();
            var item_index = self.getCustomEventIndex(event_id, new_array);
            var swapped_item = null;

            while ((item_index < (new_array.length - 1)) && (swapped_item === null || swapped_item.eventAndContentViewModel.deleted())) {
                swapped_item = new_array[item_index + 1];
                new_array[item_index + 1] = new_array[item_index];
                new_array[item_index] = swapped_item;
                item_index += 1;
            }

            self.custom_events(new_array);
        };

        self.custom_events.subscribe(function (newValue) {
            // update the order for all events when the array changes
            $.each(newValue, function (index, value) {
                value.eventAndContentViewModel.order(index);
            });
        });

        self.useTimeInput = ko.computed(function () {
            return self.send_time_type() === 'SPECIFIC_TIME' || self.send_time_type() === 'RANDOM_TIME';
        });

        self.useCasePropertyTimeInput = ko.computed(function () {
            return self.send_time_type() === 'CASE_PROPERTY_TIME';
        });

        self.init = function () {
            self.initDatePicker($("#id_schedule-start_date"));
            self.setRepeatOptionText(self.send_frequency());

            var custom_events = [];
            for (var i = 0; i < self.getNextCustomEventIndex(); i++) {
                custom_events.push(new CustomEventContainer(i));
            }
            custom_events.sort(function (item1, item2) {
                return item1.eventAndContentViewModel.order() - item2.eventAndContentViewModel.order();
            });
            self.custom_events(custom_events);
        };
    };

    var baseSelect2Handler = select2Handler.baseSelect2Handler,
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

        self.getExtraData = function () {
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
            initialPageData.get("current_values"),
            initialPageData.get("current_select2_user_recipients"),
            initialPageData.get("current_select2_user_group_recipients"),
            initialPageData.get("current_select2_user_organization_recipients"),
            initialPageData.get("current_select2_location_types"),
            initialPageData.get("current_select2_case_group_recipients"),
            initialPageData.get("current_visit_scheduler_form")
        );
        $('#create-schedule-form').koApplyBindings(scheduleViewModel);
        scheduleViewModel.init();
    });
});
