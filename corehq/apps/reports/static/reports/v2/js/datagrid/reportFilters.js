hqDefine('reports/v2/js/datagrid/reportFilters', [
    'jquery',
    'knockout',
], function (
    $,
    ko
) {
    'use strict';

    var reportFilter = function (data) {
        var self = {};

        self.title = ko.observable(data.title);
        self.name = ko.observable(data.name);
        self.value = ko.observableArray();
        self.defaultValue = ko.observable(data.defaultValue);
        self.placeholder = ko.computed(function () {
            return gettext("Select") + " " + self.title() + "...";
        });

        self.endpoint = data.endpoint;

        self.context = ko.computed(function () {
            return {
                name: self.name(),
                value: self.value(),
            };
        });

        return self;
    };

    return {
        reportFilter: reportFilter,
    };
});
