var ManageRemindersViewModel = function (initial, choices, ui_type) {
    'use strict';
    var self = this;

    self.choices = choices || {};
    self.ui_type = ui_type;

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
    self.events = ko.observable();
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
            return new ReminderEvent(event, self.choices, self.method, self.event_timing, self.event_interpretation);
        }));
    }

};

var ReminderEvent = function (eventData, choices, method, event_timing, event_interpretation) {
    'use strict';
    var self = this;
    self.choices = choices;
    self.method = method;
    self.event_timing = event_timing;
    self.event_interpretation = event_interpretation;

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
        return new ReminderMessage(message, language);
    }));
    self.isMessageVisible = ko.computed(function () {
        return (self.method() === self.choices.METHOD_SMS)
            || (self.method() === self.choices.METHOD_SMS_CALLBACK);
    });
};

var ReminderMessage = function (message, language) {
    'use strict';
    var self = this;
    self.language = ko.observable(language);
    self.message = ko.observable(message);
};
