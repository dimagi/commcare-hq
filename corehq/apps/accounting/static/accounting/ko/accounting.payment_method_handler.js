var PaymentMethodHandler = function (errorMessages) {
    'use strict';
    var self = this;

    self.errorMessages = errorMessages;

    self.costItem = ko.observable();
    self.hasCostItem = ko.computed(function () {
        return !! self.costItem();
    });
    self.stripeCard = ko.observable(new StripeCard());

    self.paymentIsComplete = ko.observable(false);
    self.paymentIsNotComplete = ko.computed(function () {
        return ! self.paymentIsComplete();
    });

    self.isSubmitDisabled = ko.computed(function () {
        return !(!! self.costItem() && self.costItem().isValid()) || self.stripeCard().isProcessing();
    });

    self.serverErrorMsg = ko.observable();
    self.showServerErrorMsg = ko.computed(function () {
        return !! self.serverErrorMsg();
    });

    self.reset = function () {
        self.paymentIsComplete(false);
        self.serverErrorMsg('');
    };

    self.processPayment = function () {
        if (self.costItem().isValid()) {
            self.stripeCard().process(self.submitForm);
        }
    };

    self.submitForm = function () {
        $('#payment-form').ajaxSubmit({
            success: function (response) {
                if (response.success) {
                    self.costItem().reset();
                    self.stripeCard().reset();
                    self.paymentIsComplete(true);
                } else {
                    self.serverErrorMsg(response);
                }
                self.stripeCard().isProcessing(false);
            },
            error: function (response, textStatus, errorThrown) {
                errorThrown = errorThrown || 500;
                self.serverErrorMsg(self.errorMessages[errorThrown]);
                self.stripeCard().isProcessing(false);
            }
        });
    };
};

var BaseCostItem = function (initData) {
    'use strict';
    var self = this;

    self.reset = function () {
        throw new Error("Missing implementation for reset");
    };

    self.isValid = function () {
        throw new Error("missing implementation for isValid");
    };
};

var Invoice = function (initData) {
    'use strict';
    BaseCostItem.call(this, initData);
    var self = this;
    self.paginatedItem = initData.paginatedItem;
    self.paginatedList = initData.paginatedList;
    self.id = ko.computed(function () {
        return self.paginatedItem.itemData().id;
    });
    self.balance = ko.computed(function () {
        return self.paginatedItem.itemData().balance;
    });
    self.invoiceNumber = ko.computed(function () {
        return self.paginatedItem.itemData().invoice_number;
    });
    self.customPaymentAmount = ko.observable(self.balance());
    self.paymentAmountType = ko.observable('full');

    self.isAmountValid = ko.computed(function () {
        try {
            var balance = parseFloat(self.balance()),
                customAmount = parseFloat(self.customPaymentAmount());
            return balance >= customAmount && customAmount >= 0.5;
        } catch (e) {
            return false;
        }
    });

    self.showAmountError = ko.computed(function () {
        return ! self.isAmountValid();
    });

    self.selectPartialPayment = function () {
        self.paymentAmountType('partial');
    };

    self.reset =  function () {
        self.customPaymentAmount(self.balance());
        self.paymentAmountType('full');
        self.paginatedList.refreshList(self.paginatedItem);
    };

    self.isValid = function () {
        return self.isAmountValid();
    };
};

Invoice.prototype = Object.create( BaseCostItem.prototype );
Invoice.prototype.constructor = Invoice;

var StripeCard = function () {
    'use strict';
    var self = this;

    self.number = ko.observable();
    self.cvc = ko.observable();
    self.expMonth = ko.observable();
    self.expYear = ko.observable();
    self.errorMsg = ko.observable();
    self.token = ko.observable();
    self.isTestMode = ko.observable(false);
    self.isProcessing = ko.observable(false);

    self.showErrors = ko.computed(function () {
        return !! self.errorMsg();
    });
    self.cleanedNumber = ko.computed(function () {
        if (self.number()) return self.number().split('-').join('');
        return null;
    });

    self.process = function (callbackOnSuccess) {
        self.isProcessing(true);
        Stripe.card.createToken({
            number: self.number(),
            cvc: self.cvc(),
            exp_month: self.expMonth(),
            exp_year: self.expYear()
        }, function (status, response) {
            if (response.error) {
                self.errorMsg(response.error.message);
                self.isProcessing(false);
            } else {
                self.errorMsg('');
                self.token(response.id);
                self.isTestMode(!response.livemode);
                if (self.token()) {
                    callbackOnSuccess();
                } else {
                    self.isProcessing(false);
                    self.errorMsg('Response from Stripe did not complete properly.');
                }
            }
        });
    };

    self.reset = function () {
        self.number('');
        self.cvc('');
        self.expMonth('');
        self.expYear('');
        self.errorMsg('');
        self.token(null);
        self.isTestMode(false);
    };
};
