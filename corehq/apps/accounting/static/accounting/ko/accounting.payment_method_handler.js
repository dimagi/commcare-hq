var PaymentMethodHandler = function (paginatedList) {
    'use strict';
    var self = this;

    self.currentBalance = ko.observable(0);
    self.statementNo = ko.observable();
    self.invoiceId = ko.observable();
    self.customPaymentAmount = ko.observable(0);
    self.paymentAmountType = ko.observable('full');
    self.stripeToken = ko.observable();
    self.displayThankYou = ko.observable(false);
    self.paginatedItem = ko.observable();
    self.paginatedList = paginatedList;

    self.stripeErrorMsg = ko.observable('');
    self.showStripeErrors = ko.computed(function () {
        return !! self.stripeErrorMsg();
    });

    self.showServerError = ko.observable(false);

    self.isCustomPaymentValid = ko.computed(function () {
        try {
            var balance = parseFloat(self.currentBalance()),
            customAmount = parseFloat(self.customPaymentAmount());
            return balance >= customAmount && customAmount >= 0.5;
        } catch (e) {
            return false;
        }
    });

    self.showCustomAmountError = ko.computed(function () {
        return !self.isCustomPaymentValid();
    });

    self.update = function (invoiceId, statementNo, balance, paginatedItem) {
        self.invoiceId(invoiceId);
        self.statementNo(statementNo);
        self.currentBalance(balance);
        self.customPaymentAmount(balance);
        self.paymentAmountType('full');
        self.stripeErrorMsg('');
        self.stripeToken(null);
        self.paginatedItem(paginatedItem);
        self.clearStripeValues();
        self.displayThankYou(false);
        self.showServerError(false);
    };

    self.processPayment = function () {
        self.processStripeCard();
    };

    self.clearStripeValues = function () {
        $('input[data-stripe="number"]').val('');
        $('input[data-stripe="cvc"]').val('');
        $('input[data-stripe="exp-month"]').val('');
        $('input[data-stripe="exp-year"]').val('');
    };

    self.processStripeCard = function () {
        Stripe.card.createToken({
            number: $('input[data-stripe="number"]').val(),
            cvc: $('input[data-stripe="cvc"]').val(),
            exp_month: $('input[data-stripe="exp-month"]').val(),
            exp_year: $('input[data-stripe="exp-year"]').val()
        }, function (status, response) {
            if (response.error) {
                self.stripeErrorMsg(response.error.message);
            } else {
                self.stripeErrorMsg('');
                self.stripeToken(response['id']);
                self.submitForm();
            }
        });
    };

    self.submitForm = function () {
        $('#payment-form').ajaxSubmit({
            success: function (response) {
                if (response.success) {
                    self.paginatedList.refreshList(self.paginatedItem());
                    self.clearStripeValues();
                    self.displayThankYou(true);
                } else {
                    self.showServerError(true);
                }
            },
            error: function (data) {
                self.showServerError(true);
            }
        });
    }
};
