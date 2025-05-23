
import $ from "jquery";
import ko from "knockout";

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
