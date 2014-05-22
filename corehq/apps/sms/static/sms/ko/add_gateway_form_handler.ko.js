var AddGatewayFormHandler = function (initial) {
    'use strict';
    var self = this;

    self.give_other_domains_access = ko.observable(initial.give_other_domains_access);
    self.showAuthorizedDomains = ko.computed(function () {
        return self.give_other_domains_access();
    });

    self.init = function () {

    };
};
