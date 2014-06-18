var BillingAccountForm = function (is_active) {
    'use strict';
    var self = this;

    self.is_active = ko.observable(is_active);
    self.showActiveAccounts = ko.computed(function () {
        return !self.is_active();
    });
};
