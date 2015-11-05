var BroadcastViewModel = function (initial_values) {
    'use strict';
    var self = this;

    self.recipient_type = ko.observable(initial_values.recipient_type);
    self.timing = ko.observable(initial_values.timing);
    self.date = ko.observable(initial_values.date);
    self.time = ko.observable(initial_values.time);
    self.case_group_id = ko.observable(initial_values.case_group_id);
    self.user_group_id = ko.observable(initial_values.user_group_id);
    self.content_type = ko.observable(initial_values.content_type);
    self.subject = ko.observable(initial_values.subject);
    self.message = ko.observable(initial_values.message);
    self.form_unique_id = ko.observable(initial_values.form_unique_id);
    self.role = ko.observable(initial_values.role);

    self.is_trial_project = initial_values.is_trial_project;
    self.displayed_email_trial_message = false;
    self.content_type.subscribe(function(newValue) {
        if(
            self.is_trial_project &&
            !self.displayed_email_trial_message &&
            newValue === 'email'
        ) {
            $('#email-trial-message-modal').modal('show');
            self.displayed_email_trial_message = true;
        }
    });

    self.showDateAndTimeSelect = ko.computed(function () {
        return self.timing() === 'LATER';
    });

    self.showSubject = ko.computed(function () {
        return self.content_type() === 'email';
    });

    self.showMessage = ko.computed(function () {
        var content_type = self.content_type();
        return content_type === 'sms' || content_type === 'email';
    });

    self.showSurveySelect = ko.computed(function () {
        return self.content_type() === 'survey';
    });

    self.showCaseGroupSelect = ko.computed(function () {
        return self.recipient_type() === 'SURVEY_SAMPLE';
    });

    self.showUserGroupSelect = ko.computed(function () {
        return self.recipient_type() === 'USER_GROUP';
    });

    self.showLocationSelect = ko.computed(function () {
        return self.recipient_type() === 'LOCATION';
    });

    self.initDatePicker = function () {
        $("input[name='date']").datepicker({dateFormat : "yy-mm-dd"});
    };

    self.initTimePicker = function () {
        var time_input = $("input[name='time']");
        time_input.timepicker({
            showMeridian: false,
            showSeconds: false,
            defaultTime: time_input.val() || false
        });
    };

    self.init = function () {
        self.initDatePicker();
        self.initTimePicker();
    };
};
