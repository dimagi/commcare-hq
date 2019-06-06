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
        self.koTemplateName = ko.observable(data.koTemplateName);

        if (data.koTemplateName.indexOf('multi') > 0) {
            self.value = ko.observableArray(data.value);
        } else {
            self.value = ko.observable(data.value);
        }

        self.isLoadingComplete = ko.observable(false);

        self.value.subscribe(function (val) {
            if (!self.isLoadingComplete() && val === undefined && data.value) {
                // make sure that when any select2 widgets are initially loading,
                // they don't accidentally set the value to undefined if it was
                // originally specified and the first page load has not completed.
                self.value(data.value);
            }
        });

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
