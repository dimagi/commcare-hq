hqDefine("app_execution/js/workflow_logs", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'app_execution/js/workflow_timing_chart',
    'hqwebapp/js/bootstrap5/components.ko',
], function ($, ko, initialPageData) {
    let logsModel = function () {
        let self = {};

        self.items = ko.observableArray();
        self.totalItems = ko.observable(initialPageData.get('total_items'));
        self.perPage = ko.observable(25);
        self.goToPage = function (page) {
            let params = {page: page, per_page: self.perPage()};
            const url = initialPageData.reverse('app_execution:logs_json');
            $.getJSON(url, params, function (data) {
                self.items(data.logs);
            });
        };

        self.onLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    $("#workflow-logs").koApplyBindings(logsModel());
});
