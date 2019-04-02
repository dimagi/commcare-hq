/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'reports/v2/js/datagrid/data_models',
    'reports/v2/js/datagrid/columns',
    'reports/v2/js/datagrid/bindingHandlers',  // for custom ko bindingHandlers
    'hqwebapp/js/knockout_bindings.ko',  // for modal bindings
], function (
    $,
    ko,
    _,
    assertProperties,
    dataModels,
    columns
) {
    'use strict';

    var datagridController = function (options) {
        assertProperties.assert(options, ['dataModel', 'columnEndpoint', 'initialColumns']);

        var self = {};

        self.data = options.dataModel;
        self.columns = ko.observableArray();

        self.reportContext = ko.computed(function () {
            return {
                existingSlugs: _.map(self.columns(), function (column) {
                    return column.slug();
                }),
            };
        });

        self.editColumnController = columns.editColumnController({
            slugEndpoint: options.columnEndpoint,
            reportContext: self.reportContext,
        });

        self.init = function () {
            self.data.init();

            _.each(options.initialColumns, function (data) {
                self.columns.push(columns.columnModel(data));
            });
        };

        self.updateColumn = function (column) {
            if (self.editColumnController.oldColumn()) {
                var replacementCols = self.columns();
                _.each(replacementCols, function (col, index) {
                    if (col.slug() === self.editColumnController.oldColumn().slug()) {
                        replacementCols[index] = columns.columnModel(column.unwrap());
                    }
                });
                self.columns(replacementCols);
            } else {
                self.columns.push(columns.columnModel(column.unwrap()));
            }
            self.editColumnController.unset();
        };

        self.deleteColumn = function () {
            var replacementCols = [];
            _.each(self.columns(), function (col) {
                if (col.slug() !== self.editColumnController.oldColumn().slug()) {
                    replacementCols.push(col);
                }
            });
            self.columns(replacementCols);
            self.editColumnController.unset();
        };

        return self;
    };

    return {
        datagridController: datagridController,
        dataModels: dataModels,
    };
});
