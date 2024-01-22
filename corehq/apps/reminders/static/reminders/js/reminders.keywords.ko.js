hqDefine("reminders/js/reminders.keywords.ko", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap3/widgets",      // .hqwebapp-select2 for survey dropdown
], function (
    $,
    ko,
    initialPageData
) {
    var keywordActionsViewModel = function (initialValues) {
        'use strict';
        var self = {};

        // load initial values
        self.keyword = ko.observable(initialValues.keyword);
        self.description = ko.observable(initialValues.description);
        self.overrideOpenSessions = ko.observable(initialValues.override_open_sessions);

        self.senderContentType = ko.observable(initialValues.sender_content_type);
        self.isMessageSMS = ko.computed(function () {
            return self.senderContentType() === 'sms';
        });
        self.isMessageSurvey = ko.computed(function () {
            return self.senderContentType() === 'survey';
        });

        self.senderMessage = ko.observable(initialValues.sender_message);
        self.senderAppAndFormUniqueId = ko.observable(initialValues.sender_app_and_form_unique_id);
        self.notifyOthers = ko.observable(initialValues.other_recipient_type !== 'none');

        self.otherRecipientType = ko.observable(initialValues.other_recipient_type);
        self.showRecipientGroup = ko.computed(function () {
            return self.otherRecipientType() === 'USER_GROUP';
        });

        self.otherRecipientId = ko.observable(initialValues.other_recipient_id);
        self.otherRecipientContentType = ko.observable(initialValues.other_recipient_content_type);
        self.notifyOthers = ko.computed(function () {
            return (self.otherRecipientContentType() === 'sms'
                || self.otherRecipientContentType() === 'survey');
        });

        self.otherRecipientMessage = ko.observable(initialValues.other_recipient_message);
        self.otherRecipientAppAndFormUniqueId = ko.observable(initialValues.other_recipient_app_and_form_unique_id);
        self.processStructuredSms = ko.observable(initialValues.process_structured_sms);
        self.structuredSmsAppAndFormUniqueId = ko.observable(initialValues.structured_sms_app_and_form_unique_id);
        self.useCustomDelimiter = ko.observable(initialValues.use_custom_delimiter);
        self.delimiter = ko.observable(initialValues.delimiter);

        self.useNamedArgs = ko.observable(initialValues.use_named_args);
        self.useNamedArgsSeparator = ko.observable(initialValues.use_named_args_separator);
        self.useJoiningCharacter = ko.computed(function () {
            return self.useNamedArgs() && self.useNamedArgsSeparator();
        });

        self.namedArgs = ko.observableArray((initialValues.named_args.length > 0) ? initialValues.named_args : [{"name": "", "xpath": ""}]);
        self.namedArgsSeparator = ko.observable(initialValues.named_args_separator);
        self.exampleStructuredSms = ko.observable("");

        self.init = function () {
            self.updateExampleStructuredSMS();
        };

        self.addNamedArg = function () {
            self.namedArgs.push({"name": "", "xpath": ""});
            self.updateExampleStructuredSMS();
        };

        self.removeNamedArg = function () {
            if (self.namedArgs().length === 1) {
                alert("You must have at least one named answer.");
            } else {
                self.namedArgs.remove(this);
            }
            self.updateExampleStructuredSMS();
        };


        self.updateExampleStructuredSMS = function () {
            var namedArgsSeparator = "";
            if (self.useNamedArgsSeparator() && self.namedArgsSeparator()) {
                namedArgsSeparator = self.namedArgsSeparator().toString().trim();
            }
            var delimiter = " ";
            if (self.useCustomDelimiter() && self.delimiter()) {
                delimiter = self.delimiter().toString().trim();
            }
            var keyword = self.keyword() ? self.keyword().toString().trim() : "";
            var example = keyword.toLowerCase();

            if (self.useNamedArgs()) {
                var toggle = false;
                for (var i = 0; i < self.namedArgs().length; i++) {
                    toggle = !toggle;
                    var argName = self.namedArgs()[i].name;
                    argName = argName ? argName.trim().toLowerCase() : "";
                    example += delimiter + argName + namedArgsSeparator + (toggle ? "123" : "456");
                }
            } else {
                example += delimiter + "123" + delimiter + "456" + delimiter + "...";
            }
            self.exampleStructuredSms(example);
            return true;
        };

        return self;
    };

    $(function () {
        var kvm = keywordActionsViewModel(initialPageData.get("current_values"));
        $('#keywords-form').koApplyBindings(kvm);
        kvm.init();
    });
});
