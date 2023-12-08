hqDefine("domain/js/manage_alerts",[
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function ($, ko, initialPageData) {

    var alertModel = function (alertData, disabled) {
        var self = alertData;
        self.isDisabled = disabled;
        return self;
    };

    var alertsViewModel = function () {
        var self = {};

        const activeAlerts = initialPageData.get('alerts').filter((alert) => {
            return alert.active;
        });
        var totalActiveAlerts = activeAlerts.length;

        var alerts = [];
        initialPageData.get('alerts').forEach(function (alert) {
            var disabled = false;
            if (totalActiveAlerts >= 3 && !alert.active) {
                disabled = true;
            }
            alerts.push(
                alertModel(alert, disabled)
            );
        });
        self.alerts = ko.observable(alerts);
        return self;
    };

    $(function () {
        $('#ko-alert-container').koApplyBindings(
            alertsViewModel()
        );
    });
});
