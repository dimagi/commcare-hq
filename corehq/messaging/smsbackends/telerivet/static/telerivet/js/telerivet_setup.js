hqDefine("telerivet/js/telerivet_setup", [
    'knockout',
    'hqwebapp/js/initial_page_data',
    'commcarehq',
], function (
    ko,
    initialPageData
) {
    var telerivetSetupModel = function () {
        var self = {};

        // Step handling
        self.step = ko.observable(0);
        self.start = ko.computed(function () { return self.step() === 0; });
        self.step1 = ko.computed(function () { return self.step() === 1; });
        self.step2 = ko.computed(function () { return self.step() === 2; });
        self.step3 = ko.computed(function () { return self.step() === 3; });
        self.finish = ko.computed(function () { return self.step() === 4; });
        self.nextStep = function () {
            self.step(self.step() + 1);
        };

        // Step 2: UI control
        self.showApiKeyGeneration = ko.observable(false);
        self.showApiInfoLocation = ko.observable(false);
        self.testSMSSent = ko.observable(false);
        self.showOutboundTroubleshoot = ko.observable(false);

        // Step 2: Outgoing SMS Form
        self.apiKey = ko.observable('');
        self.apiKeyError = ko.observable('');
        self.projectId = ko.observable('');
        self.projectIdError = ko.observable('');
        self.phoneId = ko.observable('');
        self.phoneIdError = ko.observable('');

        // Step 2: Phone Number Form
        self.testPhoneNumber = ko.observable('');
        self.testPhoneNumberError = ko.observable('');
        self.sendSmsButtonError = ko.observable(false);
        self.sendSmsButtonText = ko.computed(function () {
            return self.sendSmsButtonError() ? gettext('Server error. Try again...') : gettext('Send');
        });

        self.sendTestSMS = function () {
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse('send_sample_sms'),
                data: {
                    api_key: self.apiKey(),
                    project_id: self.projectId(),
                    phone_id: self.phoneId(),
                    test_phone_number: self.testPhoneNumber(),
                    request_token: initialPageData.get('request_token'),
                },
                success: function (data) {
                    self.sendSmsButtonError(false);
                    self.apiKeyError(data.api_key_error);
                    self.projectIdError(data.project_id_error);
                    self.phoneIdError(data.phone_id_error);
                    self.testPhoneNumberError(data.unexpected_error || data.test_phone_number_error);
                    self.testSMSSent(data.success);
                },
                error: function () {
                    self.sendSmsButtonError(true);
                },
            });
        };

        // Step 3
        self.showAddWebhookNavigation = ko.observable(false);
        self.showWebhookDetails = ko.observable(false);
        self.pollForInboundSMS = ko.observable(false);
        self.inboundSMSReceived = ko.observable(false);
        self.inboundWaitTimedOut = ko.observable(false);
        self.pollingErrorOccurred = ko.observable(false);
        self.showInboundTroubleshoot = ko.observable(false);
        self.waiting = ko.computed(function () {
            return !self.inboundSMSReceived() && !self.inboundWaitTimedOut() && !self.pollingErrorOccurred();
        });
        self.messageReceived = ko.computed(function () {
            return self.inboundSMSReceived() && !self.pollingErrorOccurred();
        });
        self.messageNotReceived = ko.computed(function () {
            return self.inboundWaitTimedOut() && !self.inboundSMSReceived() && !self.pollingErrorOccurred();
        });

        self.startInboundPolling = function () {
            self.pollForInboundSMS(true);
            self.inboundWaitTimedOut(false);
            setTimeout(function () {
                self.inboundWaitTimedOut(true);
            }, 30000);
            self.getLastInboundSMS();
        };

        self.getLastInboundSMS = function () {
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('get_last_inbound_sms'),
                data: {
                    request_token: initialPageData.get('request_token'),
                },
                success: function (data) {
                    if (data.success) {
                        if (data.found) {
                            self.inboundSMSReceived(true);
                        } else {
                            setTimeout(self.getLastInboundSMS, 10000);
                        }
                    } else {
                        self.pollingErrorOccurred(true);
                    }
                },
                error: function () {
                    // This is just an http error, for example, rather than
                    // something like a missing request token, so just retry it.
                    setTimeout(self.getLastInboundSMS, 10000);
                },
            });
        };

        // Finish
        self.setupComplete = ko.observable(false);
        self.creatingBackend = ko.observable(false);
        self.backendButtonError = ko.observable(false);
        self.backendButtonText = ko.computed(function () {
            return self.backendButtonError() ? gettext("Server error. Try again...") : gettext("Complete");
        });
        self.name = ko.observable(initialPageData.get('form_name'));
        self.nameError = ko.observable('');
        self.setAsDefault = ko.observable(initialPageData.get('form_set_as_default'));
        self.setAsDefaultError = ko.observable('');

        self.createBackend = function () {
            self.creatingBackend(true);
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse('create_backend'),
                data: {
                    name: self.name(),
                    api_key: self.apiKey(),
                    project_id: self.projectId(),
                    phone_id: self.phoneId(),
                    request_token: initialPageData.get('request_token'),
                    set_as_default: self.setAsDefault(),
                },
                success: function (data) {
                    if (data.success) {
                        self.setupComplete(true);
                        setTimeout(function () {
                            window.location.href = initialPageData.get('gateway_list_url');
                        }, 2000);
                    } else {
                        self.nameError(data.unexpected_error || data.name_error);
                        if (data.name_error) {
                            self.creatingBackend(false);
                            self.backendButtonError(false);
                        }
                    }
                },
                error: function () {
                    self.creatingBackend(false);
                    self.backendButtonError(true);
                },
            });
        };

        return self;
    };

    $(function () {
        $("#telerivet-setup").koApplyBindings(telerivetSetupModel());
    });
});
