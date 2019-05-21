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
        self.widget = ko.observable(data.widget);

        if (data.widget.indexOf('multi') > 0) {
            self.value = ko.observableArray(data.value);
        } else {
            self.value = ko.observable(data.value);
        }

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

        self.templateName = ko.computed (function () {
            return 'ko-' + self.widget();
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
