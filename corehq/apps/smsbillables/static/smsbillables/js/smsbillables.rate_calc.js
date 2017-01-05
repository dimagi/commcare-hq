var SMSRateCalculator = function (form_data) {
    'use strict';
    var self = this;

    self.gateway = ko.observable();
    self.direction = ko.observable();
    self.select2CountryCode = new Select2SmsRateHandler(form_data.country_code);
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
        self.select2CountryCode.getExtraData = function (term) {
            return {
                'gateway': self.gateway(),
                'direction': self.direction()
            }
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
                    action: 'get_rate'
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
                }
            });
        }
    };
};

var PublicSMSRateCalculator = function (form_data) {
    'use strict';
    var self = this;

    var rates = [];
    self.country_code = ko.observable();
    self.rate_table = ko.observableArray(rates);
    self.hasError = ko.observable(false);
    self.rateErrorText = ko.observable();
    self.noError = ko.computed(function () {
        return ! self.hasError();
    });
    self.calculatingRate = ko.observable(false);
    self.showTable = ko.computed(function (){
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
                    action: 'public_rate'
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
                }
            });
    };
    self.country_code.subscribe(updateRate);
};

var Select2SmsRateHandler = function (options) {
    'use strict';
    BaseSelect2Handler.call(this, options);
    var self = this;

    self.getHandlerSlug = function () {
        return 'sms_rate_calc';
    };

    self.formatSelection = function (result) {
        return result.text || (result.name + ' [' + result.rate_type + ']');
    };

    self.getInitialData = function (element) {
        return {id: element.val(), text: element.val()};
    };
};

Select2SmsRateHandler.prototype = Object.create( BaseSelect2Handler.prototype );
Select2SmsRateHandler.prototype.constructor = Select2SmsRateHandler;
