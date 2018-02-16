hqDefine('sms/js/manage_registration_invitations', [
    'jquery',
    'knockout',
    'hqwebapp/js/crud_paginated_list_init',
],
function(
    $,
    ko
) {
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
