var ManageRemindersViewModel = function (initial) {
    'use strict';
    var self = this;

    self.start_reminder_on = ko.observable(initial.start_reminder_on || 'case_date');
    self.isStartReminderCaseProperty = ko.computed(function () {
        return self.start_reminder_on() === 'case_property';
    });
    self.isStartReminderCaseDate = ko.computed(function () {
        return self.start_reminder_on() === 'case_date';
    })


};
