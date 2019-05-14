hqDefine('reports/v2/js/datagrid/report_filters', [
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
            return _.template(gettext("Select <%= title %>..."))({ title: self.title() });
        });

        self.endpoint = data.endpoint;

        self.context = ko.computed(function () {
            return {
                name: self.name(),
                value: self.value(),
            };
        });

        self.getInitialValue = function () {
            return data.value;
        };

        return self;
    };

    return {
        reportFilter: reportFilter,
    };
});
