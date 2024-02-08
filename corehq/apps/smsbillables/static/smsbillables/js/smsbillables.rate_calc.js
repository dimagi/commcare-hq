hqDefine("smsbillables/js/smsbillables.rate_calc", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/select2_handler',
    'hqwebapp/js/bootstrap3/widgets',  // the public sms page uses a .hqwebapp-select2 for country input
], function (
    $,
    ko,
    _,
    select2Handler
) {
    $(function () {
        var smsRateCalculator = function (formData) {
            'use strict';
            var self = {};

            self.gateway = ko.observable();
            self.direction = ko.observable();
            self.select2CountryCode = select2SmsRateHandler(formData.country_code);
            self.rate = ko.observable();
            self.hasError = ko.observable(false);
            self.noError = ko.computed(function () {
                return ! self.hasError();
            });
            self.calculatingRate = ko.observable(false);
            self.showRateInfo = ko.computed(function () {
                return self.rate() && ! self.calculatingRate();
            });

            self.init = function () {
                self.select2CountryCode.getExtraData = function () {
                    return {
                        'gateway': self.gateway(),
                        'direction': self.direction(),
                    };
                };
                self.select2CountryCode.init();
            };

            self.clearSelect2 = function () {
                self.select2CountryCode.clear();
                self.rate('');
            };

            self.updateRate = function () {
                if (self.select2CountryCode.value()) {
                    self.calculatingRate(true);
                    $.ajax({
                        url: '',
                        dataType: 'json',
                        type: 'POST',
                        data: {
                            gateway: self.gateway(),
                            direction: self.direction(),
                            country_code: self.select2CountryCode.value(),
                            handler: 'sms_get_rate',
                            action: 'get_rate',
                        },
                        success: function (response) {
                            self.calculatingRate(false);
                            if (response.success) {
                                self.rate(response.data.rate);
                                self.hasError(false);
                            } else {
                                self.rate(response.error);
                                self.hasError(true);
                            }
                        },
                        error: function () {
                            self.calculatingRate(false);
                            self.rate(gettext("There was an error fetching the SMS rate."));
                        },
                    });
                }
            };

            return self;
        };

        var publicSMSRateCalculator = function () {
            'use strict';
            var self = {};

            var rates = [];
            self.country_code = ko.observable();
            self.rate_table = ko.observableArray(rates);
            self.hasError = ko.observable(false);
            self.rateErrorText = ko.observable();
            self.noError = ko.computed(function () {
                return ! self.hasError();
            });
            self.calculatingRate = ko.observable(false);
            self.showTable = ko.computed(function () {
                return !self.hasError() && !self.calculatingRate();
            });
            self.showRateInfo = ko.computed(function () {
                return self.rateErrorText() && ! self.calculatingRate();
            });

            var updateRate = function () {
                self.calculatingRate(true);
                $.ajax({
                    url: '',
                    dataType: 'json',
                    type: 'POST',
                    data: {
                        country_code: self.country_code,
                        handler: 'public_sms_rate_calc',
                        action: 'public_rate',
                    },
                    success: function (response) {
                        self.calculatingRate(false);
                        self.rate_table(response.data);
                        self.hasError(false);
                        self.rateErrorText(false);
                    },
                    error: function () {
                        self.calculatingRate(false);
                        self.hasError(true);
                        self.rateErrorText(gettext("There was an error fetching the SMS rate."));
                    },
                });
            };
            self.country_code.subscribe(updateRate);

            return self;
        };

        var select2SmsRateHandler = function (options) {
            'use strict';
            var self = select2Handler.baseSelect2Handler(options);

            self.getHandlerSlug = function () {
                return 'sms_rate_calc';
            };

            self.templateSelection = function (result) {
                return result.text || (result.name + ' [' + result.rate_type + ']');
            };

            self.getInitialData = function (element) {
                return {id: element.val(), text: element.val()};
            };

            return self;
        };


        _.each($(".ko-sms-rate-calculator"), function (element) {
            var smsRateCalculatorModel = smsRateCalculator({
                country_code: {
                    fieldName: 'country_code',
                    currentValue: '',
                    placeholder: gettext('Please Select a Country Code'),
                },
            });
            $(element).koApplyBindings(smsRateCalculatorModel);
            smsRateCalculatorModel.init();
        });

        _.each($(".ko-public-sms-rate-calculator"), function (element) {
            var smsRateCalculatorModel = publicSMSRateCalculator({
                country_code: {
                    fieldName: 'country_code',
                    currentValue: '',
                },
            });
            $(element).koApplyBindings(smsRateCalculatorModel);
        });
    });
});
