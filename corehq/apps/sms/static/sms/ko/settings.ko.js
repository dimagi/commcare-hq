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

    self.showDefaultSMSResponse = ko.computed(function() {
        return self.use_default_sms_response() === "ENABLED";
    });

    self.showRestrictedSMSTimes = ko.computed(function() {
        return self.use_restricted_sms_times() === "SPECIFIC_TIMES";
    });

    self.addRestrictedSMSTime = function() {
        self.restricted_sms_times.push(new DayTimeWindow(-1, null, null));
        self.refreshTimePickers();
    };

    self.removeRestrictedSMSTime = function() {
        self.restricted_sms_times.remove(this);
    };

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
