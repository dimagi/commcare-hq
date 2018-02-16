hqDefine('sms/js/manage_registration_invitations', function() {
    $(function () {
        var RegistrationModel = function() {
            var self = this;
            self.registration_message_type = ko.observable();
            self.showCustomRegistrationMessage = ko.computed(function() {
                return self.registration_message_type() === 'CUSTOM';
            });
        };
        var registrationModel = new RegistrationModel();
        ko.applyBindings(registrationModel, $('#registration-modal').get(0));
    });
});
