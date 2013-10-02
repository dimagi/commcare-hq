var ManageRemindersViewModel = function (initial) {
    'use strict';
    var self = this;

    self.start_reminder_on = ko.observable(initial.start_reminder_on || 'case_date');
    self.isStartReminderCaseProperty = ko.computed(function () {
        return self.start_reminder_on() === 'case_property';
    });
    self.isStartReminderCaseDate = ko.computed(function () {
        return self.start_reminder_on() === 'case_date';
    });

    self.DEFAULT_MATCH_CHOICE = 'ANY_VALUE';

    self.start_match_type = ko.observable(initial.start_match_type || self.DEFAULT_MATCH_CHOICE);
    self.isStartMatchValueVisible = ko.computed(function () {
        return self.start_match_type() !== self.DEFAULT_MATCH_CHOICE;
    });

    self.start_property_offset_type = ko.observable(initial.start_property_offset_type || 'offset_delay');
    self.isStartPropertyOffsetVisible = ko.computed(function () {
        return self.start_property_offset_type() !== 'offset_immediate';
    });

    self.recipient = ko.observable(initial.recipient || 'CASE');
    self.isRecipientSubcase = ko.computed(function () {
        return self.recipient() === 'SUBCASE';
    });
};
