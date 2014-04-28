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
                    self.costItem().reset(response);
                    self.stripeCard().reset();
                    self.paymentIsComplete(true);
                    self.serverErrorMsg('');
                } else {
                    self.serverErrorMsg(response.error.message);
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

    self.reset = function (response) {
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

    self.isBalanceAtMinimum = ko.computed(function () {
        try {
            var balance = parseFloat(self.balance());
            return balance - 0.5 <= 0.0;
        } catch (e) {
            return false;
        }
    });

    self.showCustomOption = ko.computed(function () {
        return ! self.isBalanceAtMinimum();
    });

    self.isAmountWithinRange = ko.computed(function () {
        try {
            var balance = parseFloat(self.balance()),
                customAmount = parseFloat(self.customPaymentAmount());
            return balance >= customAmount && customAmount >= 0.5;
        } catch (e) {
            return false;
        }
    });

    self.maxPartialAmount = ko.computed(function () {
        return self.balance() - 0.5;
    });

    self.isLeftoverAmountEnough = ko.computed(function () {
        try {
            var balance = parseFloat(self.balance()),
                maxPartial = parseFloat(self.maxPartialAmount()),
                customAmount = parseFloat(self.customPaymentAmount());
            return customAmount == balance || customAmount <= maxPartial;
        } catch (e) {
            return false;
        }
    });

    self.showAmountRangeError = ko.computed(function () {
        return ! self.isAmountWithinRange();
    });

    self.showAmountLeftoverError = ko.computed(function () {
        return ! self.isLeftoverAmountEnough();
    });

    self.selectPartialPayment = function () {
        self.paymentAmountType('partial');
    };

    self.reset =  function (response) {
        self.customPaymentAmount(self.balance());
        self.paymentAmountType('full');
        self.paginatedList.refreshList(self.paginatedItem);
    };

    self.isValid = ko.computed(function () {
        return self.isLeftoverAmountEnough() && self.isAmountWithinRange();
    });
};

Invoice.prototype = Object.create( BaseCostItem.prototype );
Invoice.prototype.constructor = Invoice;

var CreditCostItem = function (initData) {
   'use strict';
    BaseCostItem.call(this, initData);
    var self = this;

    self.creditType = ko.observable(initData.creditType);
    self.category = ko.observable(initData.category);
    self.creditItem = initData.creditItem;
    self.amount = ko.observable(0.5);

    self.isPlanCredit = ko.computed(function () {
        return self.category() == 'product';
    });

    self.isSMSCredit = ko.computed(function () {
        return self.category() == 'feature' && self.creditType() == 'SMS';
    });

    self.isUserCredit = ko.computed(function () {
        return self.category() == 'feature' && self.creditType() == 'User';
    });

    self.reset = function (response) {
        self.creditItem.amount(response.balance);
    };

    self.isValid = function () {
        return self.amount() >= 0.5;
    };
};

CreditCostItem.ptotoptye = Object.create( BaseCostItem.prototype );
CreditCostItem.prototype.constructor = CreditCostItem;

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
