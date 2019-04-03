/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/filters', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
], function (
    $,
    ko
) {
    'use strict';

    var columnFilterModel = function (data) {
        var self = {};

        self.filterType = ko.observable(data.filterType);
        self.filterTypeTitle = ko.observable(data.filterTypeTitle);
        self.name = ko.observable(data.name);
        self.title = ko.observable(data.title);

        return self;
    };

    var appliedColumnFilterModel = function (data) {
        var self = {};

        self.filter = ko.observable(columnFilterModel(data.filter || {}));
        self.value = ko.observable(data.value);

        return self;
    };

    return {
        columnFilterModel: columnFilterModel,
        appliedColumnFilterModel: appliedColumnFilterModel,
    };
});
