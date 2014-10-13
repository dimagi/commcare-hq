function DayTimeWindow(day, start_time, end_time) {
    'use strict';
    var self = this;
    self.day = ko.observable(day);
    self.start_time = ko.observable(start_time);
    self.end_time = ko.observable(end_time);

    self.time_input_relationship_initial = function() {
        if(self.start_time() === null) {
            return "BEFORE";
        } else if(self.end_time() === null) {
            return "AFTER";
        } else {
            return "BETWEEN";
        }
    }

    self.time_input_relationship_change = function() {
        if(self.time_input_relationship() === "BEFORE") {
            self.start_time(null);
        } else if(self.time_input_relationship() === "AFTER") {
            self.end_time(null);
        }
    }

    self.time_input_relationship = ko.observable(self.time_input_relationship_initial());
}

function SettingsViewModel(initial) {
    'use strict';
    var self = this;

    self.use_default_sms_response = ko.observable();
    self.use_restricted_sms_times = ko.observable();
    self.restricted_sms_times = ko.observableArray();
    self.use_custom_case_username = ko.observable();
    self.use_custom_message_count_threshold = ko.observable();
    self.use_sms_conversation_times = ko.observable();
    self.sms_conversation_times = ko.observableArray();
    self.use_custom_chat_template = ko.observable();
    self.sms_case_registration_enabled = ko.observable();

    self.showDefaultSMSResponse = ko.computed(function() {
        return self.use_default_sms_response() === "ENABLED";
    });

    self.showCustomCaseUsername = ko.computed(function() {
        return self.use_custom_case_username() === "CUSTOM";
    });

    self.showCustomMessageCountThreshold = ko.computed(function() {
        return self.use_custom_message_count_threshold() === "CUSTOM";
    });

    self.showRestrictedSMSTimes = ko.computed(function() {
        return self.use_restricted_sms_times() === "ENABLED";
    });

    self.showRegistrationOptions = ko.computed(function() {
        return self.sms_case_registration_enabled() === "ENABLED";
    });

    self.addRestrictedSMSTime = function() {
        self.restricted_sms_times.push(new DayTimeWindow(-1, null, null));
        self.refreshTimePickers();
    };

    self.removeRestrictedSMSTime = function() {
        self.restricted_sms_times.remove(this);
    };

    self.showSMSConversationTimes = ko.computed(function() {
        return self.use_sms_conversation_times() === "ENABLED";
    });

    self.addSMSConversationTime = function() {
        self.sms_conversation_times.push(new DayTimeWindow(-1, null, null));
        self.refreshTimePickers();
    };

    self.removeSMSConversationTime = function() {
        self.sms_conversation_times.remove(this);
    };

    self.showCustomChatTemplate = ko.computed(function() {
        return self.use_custom_chat_template() === "CUSTOM";
    });

    self.refreshTimePickers = function() {
        $('[data-timeset="true"]').each(function () {
            $(this).timepicker({
                showMeridian: false,
                showSeconds: false,
                defaultTime: $(this).val() || false
            });
        });
    };

    self.init = function() {
        self.refreshTimePickers();
    };

}
