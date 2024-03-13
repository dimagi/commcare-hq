hqDefine("sms/js/settings", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/select2_handler',
    'hqwebapp/js/bootstrap3/components.ko',    // select toggle widget
    'bootstrap-timepicker/js/bootstrap-timepicker',
    'hqwebapp/js/bootstrap3/widgets', //multi-emails
], function(
    $,
    ko,
    initialPageData,
    select2Handler
) {
    $(function () {
        function dayTimeWindow(day, startTime, endTime, timeInputRelationship) {
            'use strict';
            var self = {};
            self.day = ko.observable(day);
            self.start_time = ko.observable(startTime);
            self.end_time = ko.observable(endTime);

            self.time_input_relationship_initial = function () {
                if (self.start_time() === null) {
                    return "BEFORE";
                } else if(self.end_time() === null) {
                    return "AFTER";
                } else {
                    return "BETWEEN";
                }
            };

            self.time_input_relationship = ko.observable(
                timeInputRelationship || self.time_input_relationship_initial()
            );
            return self;
        }

        function settingsViewModel(initial) {
            'use strict';
            var self = {};

            self.use_default_sms_response = ko.observable();
            self.use_restricted_sms_times = ko.observable();
            self.restricted_sms_times = ko.observableArray();
            self.use_custom_case_username = ko.observable();
            self.use_custom_message_count_threshold = ko.observable();
            self.use_sms_conversation_times = ko.observable();
            self.sms_conversation_times = ko.observableArray();
            self.use_custom_chat_template = ko.observable();
            self.sms_case_registration_enabled = ko.observable();
            self.sms_mobile_worker_registration_enabled = ko.observable();
            self.sms_case_registration_owner_id = settingsSelect2Handler(
                initial.sms_case_registration_owner_id,
                'sms_case_registration_owner_id'
            );
            self.sms_case_registration_owner_id.init();
            self.sms_case_registration_user_id = settingsSelect2Handler(
                initial.sms_case_registration_user_id,
                'sms_case_registration_user_id'
            );
            self.sms_case_registration_user_id.init();
            self.override_daily_outbound_sms_limit = ko.observable();

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

            self.showAdminAlertEmails = ko.computed(function () {
                return self.sms_mobile_worker_registration_enabled() === "ENABLED";
            });

            self.addRestrictedSMSTime = function() {
                self.restricted_sms_times.push(dayTimeWindow(-1, null, null, null));
                self.refreshTimePickers();
            };

            self.removeRestrictedSMSTime = function() {
                self.restricted_sms_times.remove(this);
            };

            self.showSMSConversationTimes = ko.computed(function() {
                return self.use_sms_conversation_times() === "ENABLED";
            });

            self.addSMSConversationTime = function() {
                self.sms_conversation_times.push(dayTimeWindow(-1, null, null, null));
                self.refreshTimePickers();
            };

            self.removeSMSConversationTime = function() {
                self.sms_conversation_times.remove(this);
            };

            self.showCustomChatTemplate = ko.computed(function() {
                return self.use_custom_chat_template() === "CUSTOM";
            });

            self.restricted_sms_times_json = ko.computed(function() {
                return ko.toJSON(self.restricted_sms_times());
            });

            self.sms_conversation_times_json = ko.computed(function() {
                return ko.toJSON(self.sms_conversation_times());
            });

            self.refreshTimePickers = function() {
                $('[data-timeset="true"]').each(function () {
                    $(this).timepicker({
                        showMeridian: false,
                        showSeconds: false,
                        defaultTime: $(this).val() || false,
                    });
                });
            };

            self.init = function() {
                self.use_default_sms_response(initial.use_default_sms_response);
                self.use_restricted_sms_times(initial.use_restricted_sms_times);
                self.use_custom_case_username(initial.use_custom_case_username);
                self.use_custom_message_count_threshold(initial.use_custom_message_count_threshold);
                self.use_sms_conversation_times(initial.use_sms_conversation_times);
                self.use_custom_chat_template(initial.use_custom_chat_template);
                self.sms_case_registration_enabled(initial.sms_case_registration_enabled);
                self.sms_mobile_worker_registration_enabled(initial.sms_mobile_worker_registration_enabled);
                self.override_daily_outbound_sms_limit(initial.override_daily_outbound_sms_limit);

                var i, window;
                if (initial.restricted_sms_times_json.length > 0) {
                    for (i = 0; i < initial.restricted_sms_times_json.length; i++) {
                        window = initial.restricted_sms_times_json[i];
                        self.restricted_sms_times.push(
                            dayTimeWindow(
                                window.day,
                                window.start_time,
                                window.end_time,
                                window.time_input_relationship
                            )
                        );
                    }
                } else {
                    self.addRestrictedSMSTime();
                }

                if (initial.sms_conversation_times_json.length > 0) {
                    for (i = 0; i < initial.sms_conversation_times_json.length; i++) {
                        window = initial.sms_conversation_times_json[i];
                        self.sms_conversation_times.push(
                            dayTimeWindow(
                                window.day,
                                window.start_time,
                                window.end_time,
                                window.time_input_relationship
                            )
                        );
                    }
                } else {
                    self.addSMSConversationTime();
                }

                self.refreshTimePickers();
            };

            return self;

        }

        var baseSelect2Handler = select2Handler.baseSelect2Handler;
        var settingsSelect2Handler = function (initialValue, fieldName) {
            /*
             * initialValue is an object like {id: ..., text: ...}
             */
            var self = baseSelect2Handler({
                fieldName: fieldName,
                multiple: false,
            });

            self.getHandlerSlug = function () {
                return 'sms_settings_async';
            };

            self.getInitialData = function () {
                return initialValue;
            };

            self.value(initialValue ? initialValue.id : '');

            return self;
        };

        var settingsModel = settingsViewModel(
            initialPageData.get("current_values")
        );
        $('#sms-settings-form').koApplyBindings(settingsModel);
        settingsModel.init();
    });
});
