import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqTempusDominus from "hqwebapp/js/tempus_dominus";
import "app_execution/js/workflow_charts";
import "hqwebapp/js/components/pagination";

let logsModel = function () {
    let self = {};

    self.statusFilter = ko.observable("");
    let allDatesText = gettext("Show All Dates");
    self.dateRange = ko.observable(allDatesText);
    self.items = ko.observableArray();
    self.totalItems = ko.observable(initialPageData.get('total_items'));
    self.perPage = ko.observable(25);
    self.goToPage = function (page) {
        let params = {page: page, per_page: self.perPage()};
        const url = initialPageData.reverse('app_execution:logs_json');
        if (self.statusFilter()) {
            params.status = self.statusFilter();
        }
        if (self.dateRange() && self.dateRange() !== allDatesText) {
            const separator = hqTempusDominus.getDateRangeSeparator(),
                dates = self.dateRange().split(separator);
            params.startDate = dates[0];
            params.endDate = dates[1] || dates[0];
        }
        $.getJSON(url, params, function (data) {
            self.items(data.logs);
        });
    };

    self.filter = ko.computed(() => {
        self.statusFilter();
        if (self.dateRange().includes(hqTempusDominus.getDateRangeSeparator())) {
            self.goToPage(1);
        }
    }).extend({throttle: 500});

    self.onLoad = function () {
        self.goToPage(1);
    };

    hqTempusDominus.createDefaultDateRangePicker(document.getElementById('id_date_range'));

    return self;
};

$("#workflow-logs").koApplyBindings(logsModel());
