hqDefine('accounting/js/credits', [
    'jquery',
    'knockout',
    'underscore',
    'accounting/js/payment_method_handler'
], function (
    $,
    ko,
    _,
    paymentMethodHandler
) {
    var creditsManager = function (products, features, paymentHandler, can_purchase_credits) {
        var self = {};

        self.paymentHandler = paymentHandler;
        self.products = ko.observableArray();
        self.features = ko.observableArray();
        self.prepayments = ko.observable();

        self.init = function () {
            _.each(products, function (product) {
                self.products.push(creditItem('product', product, paymentHandler, can_purchase_credits));
            });
            _.each(features, function (feature) {
                self.features.push(creditItem('feature', feature, paymentHandler, can_purchase_credits));
            });
            self.prepayments(prepaymentsModel(self.products, self.features, paymentHandler));
        };

        return self;
    };

    var prepaymentsModel = function(products, features, paymentHandler) {
        var self = {};
        var PrepaymentItems = paymentMethodHandler.PrepaymentItems;
        self.products = products;
        self.features = features;
        self.paymentHandler = paymentHandler;
        self.general_credit = ko.observable(generalCreditItem(paymentHandler));

        self.triggerPayment = function(paymentMethod) {
            self.paymentHandler.reset();
            self.paymentHandler.paymentMethod(paymentMethod);
            self.paymentHandler.costItem(new PrepaymentItems({
                products: self.products,
                features: self.features,
                general_credit: self.general_credit,
            }));
        };

        return self;
    };

    var generalCreditItem = function(paymentHandler) {
        var self = {};
        self.name = ko.observable("Credits");
        self.creditType = ko.observable("general_credit");
        self.addAmount = ko.observable(0);
        self.addAmountValid = ko.computed(function(){
            return  parseFloat(self.addAmount()) === 0 || (parseFloat(self.addAmount()) >= 0.5);
        });
        self.paymentHandler = paymentHandler;
        return self;
    };

    var creditItem = function (category, data, paymentHandler, can_purchase_credits) {
        var self = {};
        var CreditCostItem = paymentMethodHandler.CreditCostItem;
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
        self.canPurchaseCredits = ko.observable(can_purchase_credits);
        self.paymentHandler = paymentHandler;
        self.addAmount = ko.observable(0);

        self.addAmountValid = ko.computed(function(){
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
            self.paymentHandler.costItem(new CreditCostItem({
                creditType: self.creditType(),
                category: self.category(),
                creditItem: self,
            }));
        };

        /*
         * Return the name with the recurring interval if it exists
         */
        self.getUsageName = function() {
            return self.recurringInterval() ? self.recurringInterval() + ' ' + self.name() : self.name();
        };

        return self;
    };

    return {
        creditsManager: creditsManager,
    };
});
