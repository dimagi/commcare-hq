hqDefine("accounting/js/credits_tab", [
    'jquery',
    'knockout',
], function(
    $,
    ko
) {
    $(function() {
        var $form = $('#credit-form');
        if ($form.length) {
            var CreditFormModel = function () {
                var self = this;
                self.rateType = ko.observable("");
                self.showFeature = ko.computed(function() {
                    return self.rateType() === 'Feature';
                }, self);
            };

            var creditFormModel = new CreditFormModel();
            $form.koApplyBindings(creditFormModel);
        }
    });
});
