import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import "hqwebapp/js/bootstrap5/widgets";

$(function () {
    var alertFormModel = {
        text: ko.observable(),
        domains: ko.observable(),
        startTime: ko.observable(),
        endTime: ko.observable(),
        timezone: ko.observable(),
    };

    var alertViewModel = {
        alerts: initialPageData.get('alerts'),
    };

    $('#timezone').select2({ placeholder: 'UTC (default)' });
    $('#ko-alert-form').koApplyBindings(alertFormModel);
    $('#ko-alert-container').koApplyBindings(alertViewModel);
});
