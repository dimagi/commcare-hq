var AdjustBalanceFormModel = function () {
    var self = this;
    self.adjustmentType = ko.observable("current");
    self.showCustomAmount = ko.computed(function() {
        return self.adjustmentType() == 'credit'  ||
            self.adjustmentType() == 'debit';
    }, self);
};
