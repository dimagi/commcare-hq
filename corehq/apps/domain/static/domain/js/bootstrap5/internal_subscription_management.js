import $ from "jquery";
import ko from "knockout";
import "hqwebapp/js/bootstrap5/widgets";

$(function () {
    var viewModel = {
        subscriptionType: ko.observable($('#id_subscription_type').val() || null),
        trialLength: ko.observable(90),
    };
    viewModel.end_date = ko.computed(function () {
        var date = new Date();
        date.setHours(0, 0, 0, 0);
        date.setDate(date.getDate() + parseInt(viewModel.trialLength()));
        return date.toJSON().slice(0, 10);
    });
    $('#subscription_management').koApplyBindings(viewModel);
});
