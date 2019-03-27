/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/columns', [
    'jquery',
    'knockout',
], function (
    $,
    ko
) {
    'use strict';

    var columnModel = function (data) {
        var self = {};

        self.title = ko.observable(data.title);
        self.slug = ko.observable(data.slug);
        self.width = ko.observable(data.width || 200);

        self.unwrap = function () {
            return ko.mapping.toJS(self);
        };

        return self;
    };

    return {
        columnModel: columnModel,
    };
});
