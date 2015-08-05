var CreditsManager = function (products, features, paymentHandler, can_purchase_credits, is_plan_trial) {
    'use strict';
    var self = this;

    self.products = ko.observableArray();
    self.features = ko.observableArray();
    self.prepayments = ko.observable();

    can_purchase_credits = can_purchase_credits && !is_plan_trial;

    self.init = function () {
        _.each(products, function (product) {
            self.products.push(new CreditItem('product', product, paymentHandler, can_purchase_credits));
        });
        _.each(features, function (feature) {
            self.features.push(new CreditItem('feature', feature, paymentHandler, can_purchase_credits));
        });
        self.prepayments(new Prepayments(self.products, self.features, paymentHandler, can_purchase_credits));
    }
};

var Prepayments = function(products, features, paymentHandler, can_purchase_credits) {
    'use strict';
    var self = this;
    self.products = products;
    self.features = features;
    self.paymentHandler = paymentHandler;

    self.triggerPayment = function(paymentMethod) {
        self.paymentHandler.reset();
        self.paymentHandler.paymentMethod(paymentMethod);
        self.paymentHandler.costItem(new PrepaymentItems({
            products: self.products,
            features: self.features,
        }));
    };
};

var CreditItem = function (category, data, paymentHandler, can_purchase_credits) {
    'use strict';
    var self = this;
    self.category = ko.observable(category);
    self.name = ko.observable(data.name);
    self.creditType = ko.observable(data.type);
    self.usage = ko.observable(data.usage);
    self.remaining = ko.observable(data.remaining);
    self.monthlyFee = ko.observable(data.monthly_fee);
    self.amount = ko.observable((data.credit) ? data.credit.amount : 0);
    self.hasAmount = ko.observable(data.credit && data.credit.is_visible);
    self.canPurchaseCredits = ko.observable(can_purchase_credits);
    self.paymentHandler = paymentHandler;
    self.addAmount = ko.observable(0);

    self.addAmountValid = ko.computed(function(){
        return  parseFloat(self.addAmount()) === 0 || (parseFloat(self.addAmount()) >= 0.5);
    });

    self.isVisible = ko.computed(function () {
        return self.hasAmount() && self.canPurchaseCredits();
    });

    self.triggerPayment = function () {
        self.paymentHandler.reset();
        self.paymentHandler.costItem(new CreditCostItem({
            creditType: self.creditType(),
            category: self.category(),
            creditItem: self
        }));
    };
};
