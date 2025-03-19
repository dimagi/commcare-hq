"use strict";
hqDefine("accounting/js/credits_tab", [
    'jquery',
    'knockout',
], function (
    $,
    ko
) {
    $(function () {
        var $form = $('#credit-form');
        if ($form.length) {
            var creditFormModel = function () {
                var self = {};
                self.rateType = ko.observable("");
                self.showFeature = ko.computed(function () {
                    return self.rateType() === 'Feature';
                }, self);
                return self;
            };

            $form.koApplyBindings(creditFormModel());
        }
    });
});
