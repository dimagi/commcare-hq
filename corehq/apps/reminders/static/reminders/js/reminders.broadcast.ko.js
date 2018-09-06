hqDefine("reminders/js/reminders.broadcast.ko", function () {
    var broadcastViewModel = function (initialValues) {
        'use strict';
        var self = {};

        self.recipientType = ko.observable(initialValues.recipient_type);
        self.timing = ko.observable(initialValues.timing);
        self.date = ko.observable(initialValues.date);
        self.time = ko.observable(initialValues.time);
        self.caseGroupId = ko.observable(initialValues.case_group_id);
        self.userGroupId = ko.observable(initialValues.user_group_id);
        self.contentType = ko.observable(initialValues.content_type);
        self.subject = ko.observable(initialValues.subject);
        self.message = ko.observable(initialValues.message);
        self.formUniqueId = ko.observable(initialValues.formUniqueId);
        self.role = ko.observable(initialValues.role);

        self.isTrialProject = initialValues.isTrialProject;
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
            var contentType = self.contentType();
            return contentType === 'sms' || contentType === 'email';
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
