hqDefine("hqwebapp/js/maintenance_alerts",[
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/widgets',
], function ($, ko, initialPageData) {
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
});
