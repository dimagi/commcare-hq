hqDefine('sms/js/add_gateway_form_handler',[
    "knockout",
], function (ko) {
    var addGatewayFormHandler = function (initial) {
        'use strict';
        var self = {};

        self.share_backend = ko.observable(initial.share_backend);
        self.showAuthorizedDomains = ko.computed(function () {
            return self.share_backend();
        });

        self.phone_numbers = ko.observableArray();
        self.phone_numbers_json = ko.computed(function () {
            return ko.toJSON(self.phone_numbers());
        });

        self.use_load_balancing = ko.observable(initial.use_load_balancing);

        self.init = function () {
            if (self.use_load_balancing()) {
                var arr = initial.phone_numbers;
                for (var i = 0; i < arr.length; i++) {
                    self.phone_numbers.push(phoneNumber(arr[i].phone_number));
                }
                if (self.phone_numbers().length === 0) {
                    self.addPhoneNumber();
                }
            }
        };

        self.addPhoneNumber = function () {
            self.phone_numbers.push(phoneNumber(""));
        };

        self.removePhoneNumber = function () {
            if (self.phone_numbers().length === 1) {
                alert(initial.phone_number_required_text);
            } else {
                self.phone_numbers.remove(this);
            }
        };
        return self;
    };

    var phoneNumber = function (phoneNumber) {
        'use strict';
        var self = {};
        self.phone_number = ko.observable(phoneNumber);
        return self;
    };

    return {
        addGatewayFormHandler: addGatewayFormHandler,
    };
});
