var KeywordActionsViewModel = function (initial_values) {
    'use strict';
    var self = this;

    // load initial values
    self.keyword = ko.observable(initial_values.keyword);
    self.description = ko.observable(initial_values.description);
    self.override_open_sessions = ko.observable(initial_values.override_open_sessions);

    self.sender_content_type = ko.observable(initial_values.sender_content_type);
    self.isMessageSMS = ko.computed(function () {
        return self.sender_content_type() == 'sms';
    });
    self.isMessageSurvey = ko.computed(function () {
        return self.sender_content_type() == 'survey';
    });

    self.sender_message = ko.observable(initial_values.sender_message);
    self.sender_form_unique_id = ko.observable(initial_values.sender_form_unique_id);
    self.notify_others = ko.observable(initial_values.other_recipient_type !== 'none');

    self.other_recipient_type = ko.observable(initial_values.other_recipient_type);
    self.showRecipientGroup = ko.computed(function () {
        return self.other_recipient_type() == 'USER_GROUP';
    });

    self.other_recipient_id = ko.observable(initial_values.other_recipient_id);
    self.other_recipient_content_type = ko.observable(initial_values.other_recipient_content_type);
    self.notify_others = ko.computed(function () {
        return (self.other_recipient_content_type() === 'sms'
            || self.other_recipient_content_type() === 'survey');
    });

    self.other_recipient_message = ko.observable(initial_values.other_recipient_message);
    self.other_recipient_form_unique_id = ko.observable(initial_values.other_recipient_form_unique_id);
    self.process_structured_sms = ko.observable(initial_values.process_structured_sms);
    self.structured_sms_form_unique_id = ko.observable(initial_values.structured_sms_form_unique_id);
    self.use_custom_delimiter = ko.observable(initial_values.use_custom_delimiter);
    self.delimiter = ko.observable(initial_values.delimiter);

    self.use_named_args = ko.observable(initial_values.use_named_args);
    self.use_named_args_separator = ko.observable(initial_values.use_named_args_separator);
    self.useJoiningCharacter = ko.computed(function () {
        return self.use_named_args() && self.use_named_args_separator();
    });

    self.named_args = ko.observableArray((initial_values.named_args.length > 0) ? initial_values.named_args : [{"name" : "", "xpath" : ""}]);
    self.named_args_separator = ko.observable(initial_values.named_args_separator);
    self.example_structured_sms = ko.observable("");

    self.init = function () {
        self.updateExampleStructuredSMS();
    };

    self.addNamedArg = function() {
        self.named_args.push({"name" : "", "xpath" : ""});
        self.updateExampleStructuredSMS();
    };

    self.removeNamedArg = function() {
        if(self.named_args().length == 1) {
            alert("You must have at least one named answer.");
        } else {
            self.named_args.remove(this);
        }
        self.updateExampleStructuredSMS();
    };

    self.updateExampleStructuredSMS = function() {
        var named_args_separator = "";
        if(self.use_named_args_separator() && self.named_args_separator() != null) {
            named_args_separator = self.named_args_separator().toString().trim();
        }
        var delimiter = " ";
        if(self.use_custom_delimiter() && self.delimiter() != null) {
            delimiter = self.delimiter().toString().trim();
        }
        var keyword = (self.keyword() == null) ? "" : self.keyword().toString().trim();
        var example = keyword.toLowerCase();
        if(self.use_named_args()) {
            var toggle = false;
            for(var i = 0; i < self.named_args().length; i++) {
                toggle = !toggle;
                var arg_name = self.named_args()[i].name;
                arg_name = (arg_name == null) ? "" : arg_name.trim().toLowerCase();
                example += delimiter + arg_name + named_args_separator + (toggle ? "123" : "456");
            }
        } else {
            example += delimiter + "123" + delimiter + "456" + delimiter + "...";
        }
        self.example_structured_sms(example);
        return true;
    };
};
