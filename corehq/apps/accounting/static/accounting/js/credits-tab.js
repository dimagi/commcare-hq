var CreditFormModel = function () {
    var self = this;
    self.rateType = ko.observable("");
    self.showProduct = ko.computed(function() {
        return self.rateType() == 'Product';
    }, self);
    self.showFeature = ko.computed(function() {
        return self.rateType() == 'Feature';
    }, self);
};

var creditFormModel = new CreditFormModel();
ko.applyBindings(creditFormModel, $('#credit-form').get(0));