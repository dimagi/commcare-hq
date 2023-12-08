hqDefine("domain/js/manage_alerts",[
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function ($, ko, initialPageData) {

    var alertsViewModel = function() {
        var self = {};

        self.alerts = ko.observable(initialPageData.get('alerts'));

        return self;
    }

    $(function () {
        $('#ko-alert-container').koApplyBindings(
            alertsViewModel()
        );
    });
});
