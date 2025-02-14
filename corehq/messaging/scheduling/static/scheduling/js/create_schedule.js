import $ from "jquery";
import ko from "knockout";

import "jquery-ui/ui/widgets/datepicker";
import "bootstrap-timepicker/js/bootstrap-timepicker";

import "hqwebapp/js/components/rich_text_knockout_bindings";
import "hqwebapp/js/components/select_toggle";
import initialPageData from "hqwebapp/js/initial_page_data";
import select2Handler from "hqwebapp/js/select2_handler";

ko.bindingHandlers.useTimePicker = {
    init: function (element) {
        $(element).timepicker({
            showMeridian: false,
            showSeconds: false,
            defaultTime: $(element).val() || '',
        });
    },
    update: function () {},
};

var MessageViewModel = function (languageCode, message) {
    var self = this;

    self.language_code = ko.observable(languageCode);
    self.message = ko.observable(message);
    self.html_message = ko.observable(message);
};

var TranslationViewModel = function (languageCodes, translations) {
    var self = this;

    if (typeof translations === 'string') {
        translations = JSON.parse(translations);
    }
    translations = translations || {};
    var initialTranslate = !($.isEmptyObject(translations) || '*' in translations);

    self.translate = ko.observable(initialTranslate);
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
        languageCodes.forEach(function (languageCode) {
            self.translatedMessages.push(new MessageViewModel(languageCode, translations[languageCode]));
        });
    };

    self.loadInitialTranslatedMessages();
};

var ContentViewModel = function (initialValues) {
    var self = this;

    self.subject = new TranslationViewModel(
        initialPageData.get("language_list"),
        initialValues.subject,
    );

    self.message = new TranslationViewModel(
        initialPageData.get("language_list"),
        initialValues.message,
    );
    self.html_message = new TranslationViewModel(
        initialPageData.get("language_list"),
        initialValues.html_message,
    );

    self.survey_reminder_intervals_enabled = ko.observable(initialValues.survey_reminder_intervals_enabled);
    self.fcm_message_type = ko.observable(initialValues.fcm_message_type);

};

var EventAndContentViewModel = function (initialValues) {
    var self = this;
    ContentViewModel.call(self, initialValues);

    self.day = ko.observable(initialValues.day);
    self.time = ko.observable(initialValues.time);
    self.case_property_name = ko.observable(initialValues.case_property_name);
    self.minutesToWait = ko.observable(initialValues.minutesToWait);
    self.deleted = ko.observable(initialValues.DELETE);
    self.order = ko.observable(initialValues.ORDER);

    self.waitTimeDisplay = ko.computed(function () {
        var minutesToWait = parseInt(self.minutesToWait());
        if (minutesToWait >= 0) {
            var hours = Math.floor(minutesToWait / 60);
            var minutes = minutesToWait % 60;
            var hoursText = hours + ' ' + gettext('hour(s)');
            var minutesText = minutes + ' ' + gettext('minute(s)');
            if (hours > 0) {
                return hoursText + ', ' + minutesText;
            } else {
                return minutesText;
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

var CreateScheduleViewModel = function (initialValues, select2UserRecipients,
    select2UserGroupRecipients, select2UserOrganizationRecipients, select2LocationTypes,
    select2CaseGroupRecipients, currentVisitSchedulerForm) {
    var self = this;

    self.useCase = ko.observable(initialValues.use_case);
    self.timestamp = new Date().getTime();
    self.send_frequency = ko.observable(initialValues.send_frequency);
    self.weekdays = ko.observableArray(initialValues.weekdays || []);
    self.days_of_month = ko.observableArray(initialValues.days_of_month || []);
    self.send_time = ko.observable(initialValues.send_time);
    self.send_time_type = ko.observable(initialValues.send_time_type);
    self.start_date = ko.observable(initialValues.start_date);
    self.start_date_type = ko.observable(initialValues.start_date_type);
    self.start_offset_type = ko.observable(initialValues.start_offset_type);
    self.repeat = ko.observable(initialValues.repeat);
    self.repeat_every = ko.observable(initialValues.repeat_every);
    self.stop_type = ko.observable(initialValues.stop_type);
    self.occurrences = ko.observable(initialValues.occurrences);
    self.recipient_types = ko.observableArray(initialValues.recipient_types || []);
    $('#id_schedule-recipient_types').select2();

    self.user_recipients = new recipientsSelect2Handler(select2UserRecipients,
        initialValues.user_recipients, 'schedule-user_recipients');
    self.user_recipients.init();

    self.user_group_recipients = new recipientsSelect2Handler(select2UserGroupRecipients,
        initialValues.user_group_recipients, 'schedule-user_group_recipients');
    self.user_group_recipients.init();

    self.user_organization_recipients = new recipientsSelect2Handler(select2UserOrganizationRecipients,
        initialValues.user_organization_recipients, 'schedule-user_organization_recipients');
    self.user_organization_recipients.init();

    self.include_descendant_locations = ko.observable(initialValues.include_descendant_locations);
    self.restrict_location_types = ko.observable(initialValues.restrict_location_types);

    self.location_types = new recipientsSelect2Handler(select2LocationTypes,
        initialValues.location_types, 'schedule-location_types');
    self.location_types.init();

    self.case_group_recipients = new recipientsSelect2Handler(select2CaseGroupRecipients,
        initialValues.case_group_recipients, 'schedule-case_group_recipients');
    self.case_group_recipients.init();

    self.reset_case_property_enabled = ko.observable(initialValues.reset_case_property_enabled);
    self.stop_date_case_property_enabled = ko.observable(initialValues.stop_date_case_property_enabled);
    self.submit_partially_completed_forms = ko.observable(initialValues.submit_partially_completed_forms);

    self.is_trial_project = initialValues.is_trial_project;
    self.displayed_email_trial_message = false;
    self.content = ko.observable(initialValues.content);
    self.standalone_content_form = new ContentViewModel(initialValues.standalone_content_form);
    self.custom_events = ko.observableArray();
    self.visit_scheduler_app_and_form_unique_id = new formSelect2Handler(currentVisitSchedulerForm,
        'schedule-visit_scheduler_app_and_form_unique_id', self.timestamp);
    self.visit_scheduler_app_and_form_unique_id.init();

    self.use_user_data_filter = ko.observable(initialValues.use_user_data_filter);
    self.capture_custom_metadata_item = ko.observable(initialValues.capture_custom_metadata_item);
    self.editing_custom_immediate_schedule = ko.observable(initialValues.editing_custom_immediate_schedule);

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

    self.calculateDailyEndDate = function (startDateMilliseconds, repeatEvery, occurrences) {
        var millisecondsInADay = 24 * 60 * 60 * 1000;
        var daysUntilEndDate = (occurrences - 1) * repeatEvery;
        return new Date(startDateMilliseconds + (daysUntilEndDate * millisecondsInADay));
    };

    self.calculateWeeklyEndDate = function (startDateMilliseconds, repeatEvery, occurrences) {
        var millisecondsInADay = 24 * 60 * 60 * 1000;
        var jsStartDayOfWeek = new Date(startDateMilliseconds).getUTCDay();
        var pythonStartDayOfWeek = (jsStartDayOfWeek + 6) % 7;
        var offsetToLastWeekdayInSchedule = null;
        for (var i = 0; i < 7; i++) {
            var currentWeekday = (pythonStartDayOfWeek + i) % 7;
            if (self.weekdays().indexOf(currentWeekday.toString()) !== -1) {
                offsetToLastWeekdayInSchedule = i;
            }
        }
        if (offsetToLastWeekdayInSchedule === null) {
            return null;
        }

        return new Date(
            startDateMilliseconds +
            offsetToLastWeekdayInSchedule * millisecondsInADay +
            (occurrences - 1) * 7 * repeatEvery * millisecondsInADay,
        );
    };

    self.calculateMonthlyEndDate = function (startDateMilliseconds, repeatEvery, occurrences) {
        var lastDay = null;
        self.days_of_month().forEach(function (value) {
            value = parseInt(value);
            if (lastDay === null) {
                lastDay = value;
            } else if (lastDay > 0) {
                if (value < 0) {
                    lastDay = value;
                } else if (value > lastDay) {
                    lastDay = value;
                }
            } else {
                if (value < 0 && value > lastDay) {
                    lastDay = value;
                }
            }
        });
        if (lastDay === null) {
            return null;
        }

        var endDate = new Date(startDateMilliseconds);
        endDate.setUTCMonth(endDate.getUTCMonth() + (occurrences - 1) * repeatEvery);
        if (lastDay < 0) {
            endDate.setUTCMonth(endDate.getUTCMonth() + 1);
            // Using a value of 0 sets it to the last day of the previous month
            endDate.setUTCDate(lastDay + 1);
        } else {
            endDate.setUTCDate(lastDay);
        }
        return endDate;
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
        var startDateMilliseconds = Date.parse(self.start_date());
        var repeatEvery = self.calculateRepeatEvery();
        var occurrences = self.calculateOccurrences();

        if (self.start_date_type() && self.start_date_type() !== 'SPECIFIC_DATE') {
            return '';
        }

        if (isNaN(startDateMilliseconds) || isNaN(occurrences) || isNaN(repeatEvery)) {
            return '';
        }

        var endDate = null;
        if (self.send_frequency() === 'daily') {
            endDate = self.calculateDailyEndDate(startDateMilliseconds, repeatEvery, occurrences);
        } else if (self.send_frequency() === 'weekly') {
            endDate = self.calculateWeeklyEndDate(startDateMilliseconds, repeatEvery, occurrences);
        } else if (self.send_frequency() === 'monthly') {
            endDate = self.calculateMonthlyEndDate(startDateMilliseconds, repeatEvery, occurrences);
        }

        if (endDate) {
            return endDate.toJSON().substr(0, 10);
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
            $('#id_custom_event_empty_form_container').html().replace(/__prefix__/g, id),
        );
        $('#id_custom-event-TOTAL_FORMS').val(id + 1);
        self.custom_events.push(new CustomEventContainer(id));
    };

    self.markCustomEventDeleted = function (eventId) {
        $.each(self.custom_events(), function (index, value) {
            if (value.event_id === eventId) {
                value.eventAndContentViewModel.deleted(true);
            }
        });
    };

    self.getCustomEventIndex = function (eventId, arr) {
        var itemIndex = null;
        $.each(arr, function (index, value) {
            if (value.event_id === eventId) {
                itemIndex = index;
            }
        });
        return itemIndex;
    };

    self.moveCustomEventUp = function (eventId) {
        var newArray = self.custom_events();
        var itemIndex = self.getCustomEventIndex(eventId, newArray);
        var swappedItem = null;

        while (itemIndex > 0 && (swappedItem === null || swappedItem.eventAndContentViewModel.deleted())) {
            swappedItem = newArray[itemIndex - 1];
            newArray[itemIndex - 1] = newArray[itemIndex];
            newArray[itemIndex] = swappedItem;
            itemIndex -= 1;
        }

        self.custom_events(newArray);
    };

    self.moveCustomEventDown = function (eventId) {
        var newArray = self.custom_events();
        var itemIndex = self.getCustomEventIndex(eventId, newArray);
        var swappedItem = null;

        while ((itemIndex < (newArray.length - 1)) && (swappedItem === null || swappedItem.eventAndContentViewModel.deleted())) {
            swappedItem = newArray[itemIndex + 1];
            newArray[itemIndex + 1] = newArray[itemIndex];
            newArray[itemIndex] = swappedItem;
            itemIndex += 1;
        }

        self.custom_events(newArray);
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

        var customEvents = [];
        for (var i = 0; i < self.getNextCustomEventIndex(); i++) {
            customEvents.push(new CustomEventContainer(i));
        }
        customEvents.sort(function (item1, item2) {
            return item1.eventAndContentViewModel.order() - item2.eventAndContentViewModel.order();
        });
        self.custom_events(customEvents);
    };
};

var baseSelect2Handler = select2Handler.baseSelect2Handler,
    recipientsSelect2Handler = function (initialObjectList, initialCommaSeparatedList, field) {
        /*
         * initialObjectList is a list of {id: ..., text: ...} objects representing the initial value
         *
         * intial_comma_separated_list is a string representation of initialObjectList consisting of just
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
            return initialObjectList;
        };

        self.value(initialCommaSeparatedList);

        return self;
    };

recipientsSelect2Handler.prototype = Object.create(recipientsSelect2Handler.prototype);
recipientsSelect2Handler.prototype.constructor = recipientsSelect2Handler;

var formSelect2Handler = function (initialObject, field, timestamp) {
    /*
     * initialObject is an {id: ..., text: ...} object representing the initial value
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
        return initialObject;
    };

    self.value(initialObject ? initialObject.id : '');

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
        initialPageData.get("current_visit_scheduler_form"),
    );
    $('#create-schedule-form').koApplyBindings(scheduleViewModel);
    scheduleViewModel.init();
});
