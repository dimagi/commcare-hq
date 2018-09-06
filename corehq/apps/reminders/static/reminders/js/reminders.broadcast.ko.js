hqDefine("reminders/js/reminders.broadcast.ko", function () {
    var broadcastViewModel = function (initial_values) {
        'use strict';
        var self = {};

        self.recipientType = ko.observable(initial_values.recipient_type);
        self.timing = ko.observable(initial_values.timing);
        self.date = ko.observable(initial_values.date);
        self.time = ko.observable(initial_values.time);
        self.caseGroupId = ko.observable(initial_values.case_group_id);
        self.userGroupId = ko.observable(initial_values.user_group_id);
        self.contentType = ko.observable(initial_values.content_type);
        self.subject = ko.observable(initial_values.subject);
        self.message = ko.observable(initial_values.message);
        self.formUniqueId = ko.observable(initial_values.formUniqueId);
        self.role = ko.observable(initial_values.role);

        self.isTrialProject = initial_values.isTrialProject;
        self.displayedEmailTrialMessage = false;
        self.contentType.subscribe(function (newValue) {
            if (
                self.is_trial_project &&
                !self.displayed_email_trial_message &&
                newValue === 'email'
            ) {
                $('#email-trial-message-modal').modal('show');
                self.displayedEmailTrialMessage = true;
            }
        });

        self.showDateAndTimeSelect = ko.computed(function () {
            return self.timing() === 'LATER';
        });

        self.showSubject = ko.computed(function () {
            return self.contentType() === 'email';
        });

        self.showMessage = ko.computed(function () {
            var content_type = self.contentType();
            return content_type === 'sms' || content_type === 'email';
        });

        self.showSurveySelect = ko.computed(function () {
            return self.contentType() === 'survey';
        });

        self.showCaseGroupSelect = ko.computed(function () {
            return self.recipientType() === 'SURVEY_SAMPLE';
        });

        self.showUserGroupSelect = ko.computed(function () {
            return self.recipientType() === 'USER_GROUP';
        });

        self.showLocationSelect = ko.computed(function () {
            return self.recipientType() === 'LOCATION';
        });

        self.initDatePicker = function () {
            $("input[name='date']").datepicker({dateFormat: "yy-mm-dd"});
        };

        self.initTimePicker = function () {
            var time_input = $("input[name='time']");
            time_input.timepicker({
                showMeridian: false,
                showSeconds: false,
                defaultTime: time_input.val() || false,
            });
        };

        self.init = function () {
            self.initDatePicker();
            self.initTimePicker();
        };

        return self;
    };

    $(function () {
        var bvm = broadcastViewModel(hqImport("hqwebapp/js/initial_page_data").get("current_values"));
        $('#broadcast-form').koApplyBindings(bvm);
        bvm.init();
    });
});
