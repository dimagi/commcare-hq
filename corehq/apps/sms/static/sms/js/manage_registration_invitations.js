hqDefine('sms/js/manage_registration_invitations', [
    'jquery',
    'knockout',
    'hqwebapp/js/crud_paginated_list_init',
],
function (
    $,
    ko
) {
    $(function () {
        var registrationModel = function () {
            var self = {};
            self.registration_message_type = ko.observable();
            self.showCustomRegistrationMessage = ko.computed(function () {
                return self.registration_message_type() === 'CUSTOM';
            });
            return self;
        };
        ko.applyBindings(registrationModel(), $('#registration-modal').get(0));
    });
});
