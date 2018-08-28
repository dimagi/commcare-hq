hqDefine("telerivet/js/telerivet_setup", [
    'knockout',
    'hqwebapp/js/initial_page_data',
], function(
    ko,
    initialPageData
) {
    var telerivetSetupModel = function() {
        var self = {};

        // Step handling
        self.step = ko.observable(0);
        self.start = ko.computed(function() { return self.step() === 0; });
        self.step1 = ko.computed(function() { return self.step() === 1; });
        self.step2 = ko.computed(function() { return self.step() === 2; });
        self.step3 = ko.computed(function() { return self.step() === 3; });
        self.finish = ko.computed(function() { return self.step() === 4; });
        self.nextStep = function() {
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

        self.sendTestSMS = function() {
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
                success: function(data) {
                    $('#id_send_sms_button').text(gettext("Send"));
                    self.apiKeyError(data.api_key_error);
                    self.projectIdError(data.project_id_error);
                    self.phoneIdError(data.phone_id_error);
                    self.testPhoneNumberError(data.unexpected_error || data.test_phone_number_error);
                    self.testSMSSent(data.success);
                },
                error: function(data) {
                    $('#id_send_sms_button').text(gettext("Server error. Try again..."));
                },
            });
        };

        // Step 3
        self.showAddWebhookNavigation = ko.observable(false);
        self.showWebhookDetails = ko.observable(false);
        self.pollForInboundSMS = ko.observable(true);       // TODO
        self.inboundSMSReceived = ko.observable(true);      // TODO
        self.inboundWaitTimedOut = ko.observable(false);
        self.pollingErrorOccurred = ko.observable(false);
        self.showInboundTroubleshoot = ko.observable(false);
        self.waiting = ko.computed(function() {
            return !self.inboundSMSReceived() && !self.inboundWaitTimedOut() && !self.pollingErrorOccurred();
        });
        self.messageReceived = ko.computed(function() {
            return self.inboundSMSReceived() && !self.pollingErrorOccurred();
        });
        self.messageNotReceived = ko.computed(function() {
            return self.inboundWaitTimedOut() && !self.inboundSMSReceived() && !self.pollingErrorOccurred();
        });

        // Finish
        self.setupComplete = ko.observable(false);

        return self;
    };

    $(function() {
        $("#telerivet-setup").koApplyBindings(telerivetSetupModel());
    });

    /*
    var globalProjectId = '';
    var globalPhoneId = '';
    var globalTestPhoneNumber = '';
    var globalTestSMSSent = false;

    telerivetSetupApp.controller('TelerivetSetupController', function($scope, djangoRMI) {
        // model attributes
        $scope.projectId = globalProjectId;
        $scope.phoneId = globalPhoneId;
        $scope.testPhoneNumber = globalTestPhoneNumber;
        $scope.name = initialPageData('form_name');
        $scope.setAsDefault = initialPageData('form_set_as_default');

        // error messages
        $scope.projectIdError = null;
        $scope.phoneIdError = null;
        $scope.testPhoneNumberError = null;
        $scope.nameError = null;
        $scope.setAsDefaultError = null;

        // control flow variables
        $scope.testSMSSent = globalTestSMSSent;
        $scope.pollForInboundSMS = false;
        $scope.pollingErrorOccurred = false;
        $scope.inboundSMSReceived = false;
        $scope.inboundWaitTimedOut = false;
        $scope.setupComplete = false;

        $scope.createBackend = function() {
            $('#id_create_backend').prop('disabled', true);
            djangoRMI.create_backend({
                name: $scope.name,
                api_key: $scope.apiKey,
                project_id: $scope.projectId,
                phone_id: $scope.phoneId,
                request_token: initialPageData('request_token'),
                set_as_default: $scope.setAsDefault
            })
            .success(function(data) {
                if(data.success) {
                    $scope.setupComplete = true;
                    setTimeout(function() {
                        window.location.href = initialPageData('gateway_list_url')
                    }, 2000);
                } else {
                    $scope.nameError = data.unexpected_error || data.name_error;
                    if(data.name_error) {
                        $('#id_create_backend')
                        .prop('disabled', false)
                        .text(gettext("Complete"));
                    }
                }
            })
            .error(function() {
                $('#id_create_backend')
                .prop('disabled', false)
                .text(gettext("Server error. Try again..."));
            });
        };

        $scope.getLastInboundSMS = function() {
            djangoRMI.get_last_inbound_sms({
                request_token: initialPageData('request_token'),
            })
            .success(function(data) {
                if(data.success) {
                    if(data.found) {
                        $scope.inboundSMSReceived = true;
                    } else {
                        setTimeout($scope.getLastInboundSMS, 10000);
                    }
                } else {
                    $scope.pollingErrorOccurred = true;
                }
            })
            .error(function() {
                // This is just an http error, for example, rather than
                // something like a missing request token, so just retry it.
                setTimeout($scope.getLastInboundSMS, 10000);
            });
        };

        $scope.startInboundPolling = function() {
            $scope.pollForInboundSMS = true;
            $scope.inboundWaitTimedOut = false;
            setTimeout(function() {
                $scope.inboundWaitTimedOut = true;
            }, 30000);
            $scope.getLastInboundSMS();
        };

        // TODO: Figure out if there's a better way to deal with these scope issues
        $scope.$watch('apiKey', function(newValue, oldValue) {
            globalApiKey = newValue;
            $scope.testSMSSent = false;
        });
        $scope.$watch('projectId', function(newValue, oldValue) {
            globalProjectId = newValue;
            $scope.testSMSSent = false;
        });
        $scope.$watch('phoneId', function(newValue, oldValue) {
            globalPhoneId = newValue;
            $scope.testSMSSent = false;
        });
        $scope.$watch('testPhoneNumber', function(newValue, oldValue) {
            globalTestPhoneNumber = newValue;
        });
        $scope.$watch('testSMSSent', function(newValue, oldValue) {
            globalTestSMSSent = newValue;
        });
    });*/
});
