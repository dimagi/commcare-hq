"use strict";
hqDefine('accounting/js/credits', [
    'jquery',
    'knockout',
    'underscore',
    'accounting/js/payment_method_handler',
    'eonasdan-bootstrap-datetimepicker/build/js/bootstrap-datetimepicker.min',
], function (
    $,
    ko,
    _,
    paymentMethodHandler
) {
    var creditsManager = function (products, features, paymentHandler, canPurchaseCredits) {
        var self = {};

        self.paymentHandler = paymentHandler;
        self.products = ko.observableArray();
        self.features = ko.observableArray();
        self.prepayments = ko.observable();

        self.init = function () {
            _.each(products, function (product) {
                self.products.push(creditItem('product', product, paymentHandler, canPurchaseCredits));
            });
            _.each(features, function (feature) {
                self.features.push(creditItem('feature', feature, paymentHandler, canPurchaseCredits));
            });
            self.prepayments(prepaymentsModel(self.products, self.features, paymentHandler));
        };

        return self;
    };

    var prepaymentsModel = function (products, features, paymentHandler) {
        var self = {};
        var prepaymentItems = paymentMethodHandler.prepaymentItems;
        self.products = products;
        self.features = features;
        self.paymentHandler = paymentHandler;
        self.cc_general_credit = ko.observable(ccGeneralCreditItem(paymentHandler));
        self.invoice_general_credit = ko.observable(invoiceGeneralCreditItem(paymentHandler));

        self.triggerPayment = function (paymentMethod) {
            self.paymentHandler.reset();
            self.paymentHandler.paymentMethod(paymentMethod);
            self.paymentHandler.costItem(prepaymentItems({
                products: self.products,
                features: self.features,
                general_credit: self.cc_general_credit,
                invoice_credit: self.invoice_general_credit,
            }));
        };
        return self;
    };

    var ccGeneralCreditItem = function (paymentHandler) {
        var self = {};
        self.name = ko.observable("Credits");
        self.creditType = ko.observable("cc_general_credit");
        self.addAmount = ko.observable(0);
        self.addAmountValid = ko.computed(function () {
            return  parseFloat(self.addAmount()) === 0 || (parseFloat(self.addAmount()) >= 0.5);
        });
        self.paymentHandler = paymentHandler;
        return self;
    };

    var invoiceGeneralCreditItem = function (paymentHandler) {
        var self = {};
        self.date_start = ko.observable();
        self.date_end = ko.observable();
        self.name = ko.observable("Unit Cost");
        self.creditType = ko.observable("invoice_general_credit");
        self.quantity = ko.observable(1);
        self.addAmount = ko.observable(0);
        self.addAmountValid = ko.computed(function () {
            return  parseFloat(self.addAmount()) === 0 || (parseFloat(self.addAmount()) >= 0.5);
        });
        self.paymentHandler = paymentHandler;
        return self;
    };

    var creditItem = function (category, data, paymentHandler, canPurchaseCredits) {
        var self = {};
        var creditCostItem = paymentMethodHandler.creditCostItem;
        self.category = ko.observable(category);
        self.name = ko.observable(data.name);
        self.recurringInterval = ko.observable(data.recurring_interval);
        self.creditType = ko.observable(data.type);
        self.usage = ko.observable(data.usage);
        self.limit = ko.observable(data.limit);
        self.remaining = ko.observable(data.remaining);
        self.monthlyFee = ko.observable(data.monthly_fee);
        self.amount = ko.observable((data.subscription_credit) ? data.subscription_credit.amount : 0);
        self.accountAmount = ko.observable((data.account_credit) ? data.account_credit.amount : 0);
        self.hasAmount = ko.observable(data.subscription_credit && data.subscription_credit.is_visible);
        self.hasAccountAmount = ko.observable(data.account_credit && data.account_credit.is_visible);
        self.canPurchaseCredits = ko.observable(canPurchaseCredits);
        self.paymentHandler = paymentHandler;
        self.addAmount = ko.observable(0);

        self.addAmountValid = ko.computed(function () {
            return  parseFloat(self.addAmount()) === 0 || (parseFloat(self.addAmount()) >= 0.5);
        });

        self.isVisible = ko.computed(function () {
            return self.hasAmount() && self.canPurchaseCredits();
        });

        self.isAccountVisible = ko.computed(function () {
            return self.hasAccountAmount() && self.canPurchaseCredits();
        });

        self.triggerPayment = function () {
            self.paymentHandler.reset();
            self.paymentHandler.costItem(creditCostItem({
                creditType: self.creditType(),
                category: self.category(),
                creditItem: self,
            }));
        };

        /*
         * Return the name with the recurring interval if it exists
         */
        self.getUsageName = function () {
            return self.recurringInterval() ? self.recurringInterval() + ' ' + self.name() : self.name();
        };

        return self;
    };

    $(function () {
        $('#paymentModal').on('shown.bs.modal', function () {
            $("#prepay-date-start").datetimepicker({
                format: "YYYY-MM-DD",
            });
            $("#prepay-date-end").datetimepicker({
                format: "YYYY-MM-DD",
            });
        });
    });

    return {
        creditsManager: creditsManager,
    };
});
