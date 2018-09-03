hqDefine("reminders/js/reminders.keywords.ko", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    ko,
    initialPageData
) {
    var keywordActionsViewModel = function (initial_values) {
        'use strict';
        var self = {};

        // load initial values
        self.keyword = ko.observable(initial_values.keyword);
        self.description = ko.observable(initial_values.description);
        self.overrideOpenSessions = ko.observable(initial_values.override_open_sessions);

        self.senderContentType = ko.observable(initial_values.sender_content_type);
        self.isMessageSMS = ko.computed(function () {
            return self.senderContentType() === 'sms';
        });
        self.isMessageSurvey = ko.computed(function () {
            return self.senderContentType() === 'survey';
        });

        self.senderMessage = ko.observable(initial_values.sender_message);
        self.senderFormUniqueId = ko.observable(initial_values.sender_form_unique_id);
        self.notifyOthers = ko.observable(initial_values.other_recipient_type !== 'none');

        self.otherRecipientType = ko.observable(initial_values.other_recipient_type);
        self.showRecipientGroup = ko.computed(function () {
            return self.otherRecipientType() === 'USER_GROUP';
        });

        self.otherRecipientId = ko.observable(initial_values.other_recipient_id);
        self.otherRecipientContentType = ko.observable(initial_values.other_recipient_content_type);
        self.notifyOthers = ko.computed(function () {
            return (self.otherRecipientContentType() === 'sms'
                || self.otherRecipientContentType() === 'survey');
        });

        self.otherRecipientMessage = ko.observable(initial_values.other_recipient_message);
        self.otherRecipientFormUniqueId = ko.observable(initial_values.other_recipient_form_unique_id);
        self.processStructuredSms = ko.observable(initial_values.process_structured_sms);
        self.structuredSmsFormUniqueId = ko.observable(initial_values.structured_sms_form_unique_id);
        self.useCustomDelimiter = ko.observable(initial_values.use_custom_delimiter);
        self.delimiter = ko.observable(initial_values.delimiter);

        self.useNamedArgs = ko.observable(initial_values.use_named_args);
        self.useNamedArgsSeparator = ko.observable(initial_values.use_named_args_separator);
        self.useJoiningCharacter = ko.computed(function () {
            return self.useNamedArgs() && self.useNamedArgsSeparator();
        });


        self.namedArgs = ko.observableArray((initial_values.named_args.length > 0) ? initial_values.named_args : [{"name": "", "xpath": ""}]);
        self.namedArgsSeparator = ko.observable(initial_values.named_args_separator);
        self.exampleStructuredSms = ko.observable("");

        self.init = function () {
            self.updateExampleStructuredSMS();
        };

        self.addNamedArg = function () {
            self.namedArgs.push({"name" : "", "xpath" : ""});
            self.updateExampleStructuredSMS();
        };

        self.removeNamedArg = function() {
            if(self.namedArgs().length === 1) {
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

            if(self.useNamedArgs()) {
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
