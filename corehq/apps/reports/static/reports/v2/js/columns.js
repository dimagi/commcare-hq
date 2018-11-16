/**
 * todo add docstring
 */

hqDefine('reports/v2/js/columns', [
    'underscore',
    'hqwebapp/js/assert_properties',
    'reports/v2/js/formatters',
], function (
    _,
    assertProperties,
    formatters
) {
    'use strict';

    var column = function (data) {
        assertProperties.assert(data, ['title', 'slug'], ['format']);

        var self = {};

        self.title = data.title;
        self.slug = data.slug;
        self.format = data.format || 'default';

        self.getFormatter = function () {
            var formatterFn = formatters[self.format];
            if (!formatterFn) {
                formatterFn = formatters.default;
            }
            return formatterFn;
        };

        self.getOptions = function () {
            /**
             * Returns the options formatted as datatables expects them.
             * reference: https://datatables.net/reference/option/columns
             */
            return {
                title: self.title,
                data: self.slug,
                render: self.getFormatter(),
            };
        };

        return self;
    };

    var columnFilter = function () {
        // todo
        var self = {};

        self.columns = [];

        self.init = function () {

        };

        return self;
    };

    return {
        getColumnFilter: function (data) {
            return columnFilter(data);
        },
        getColumn: function (data) {
            return column(data);
        },
    };
});
