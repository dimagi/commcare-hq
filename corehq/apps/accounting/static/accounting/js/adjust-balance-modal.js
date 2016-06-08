hqDefine('accounting/js/adjust-balance-modal.js', function () {
    var AdjustBalanceFormModel = function () {
        var self = this;
        self.adjustmentType = ko.observable("current");
        self.showCustomAmount = ko.computed(function() {
            return self.adjustmentType() === 'credit'  ||
                self.adjustmentType() === 'debit';
        }, self);
    };
    return {AdjustBalanceFormModel: AdjustBalanceFormModel};
});
