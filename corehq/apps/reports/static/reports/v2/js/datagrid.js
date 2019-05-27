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
    'reports/v2/js/datagrid/report_filters',
    'reports/v2/js/datagrid/binding_handlers',  // for custom ko bindingHandlers
    'hqwebapp/js/knockout_bindings.ko',  // for modal bindings
], function (
    $,
    ko,
    _,
    assertProperties,
    dataModels,
    columns,
    reportFilters
) {
    'use strict';

    var datagridController = function (options) {
        assertProperties.assert(options, [
            'dataModel',
            'columnEndpoint',
            'initialColumns',
            'columnFilters',
            'reportFilters',
        ], [
            'hideColumnFilterCondition',
            'noDeleteColumnCondition',
            'unsortableColumnNames',
        ]);

        var self = {};

        self.data = options.dataModel;
        self.reportFilters = ko.observableArray(_.map(options.reportFilters, function (data) {
            return reportFilters.reportFilter(data);
        }));
        self.columns = ko.observableArray();

        self.editColumnController = columns.editColumnController({
            endpoint: options.columnEndpoint,
            availableFilters: options.columnFilters,
            hideColumnFilterCondition: options.hideColumnFilterCondition,
            noDeleteColumnCondition: options.noDeleteColumnCondition,
        });

        self.init = function () {

            _.each(options.initialColumns, function (data) {
                self.columns.push(columns.columnModel(data));
            });

            self.reportContext = ko.computed(function () {
                return {
                    existingColumnNames: _.map(self.columns(), function (column) {
                        return column.name();
                    }),
                    columns: _.map(self.columns(), function (column) {
                        return column.context();
                    }),
                    reportFilters: _.map(self.reportFilters(), function (reportFilter) {
                        return reportFilter.context();
                    }),
                };
            });

            self.data.init(self.reportContext, self.reportFilters);
            self.editColumnController.init(self.reportContext);
        };

        self.updateColumn = function (column) {
            if (self.editColumnController.oldColumn()) {
                var replacementCols = self.columns();
                _.each(replacementCols, function (col, index) {
                    if (col.name() === self.editColumnController.oldColumn().name()) {
                        replacementCols[index] = columns.columnModel(column.unwrap());
                    }
                });
                self.columns(replacementCols);
            } else {
                self.columns.push(columns.columnModel(column.unwrap()));
            }
            if (self.editColumnController.hasFilterUpdate()) {
                self.data.refresh();
            }
            self.editColumnController.unset();
        };

        self.deleteColumn = function () {
            var replacementCols = [];
            _.each(self.columns(), function (col) {
                if (col.name() !== self.editColumnController.oldColumn().name()) {
                    replacementCols.push(col);
                }
            });
            self.columns(replacementCols);
            if (self.editColumnController.oldColumn().appliedFilters.length > 0) {
                // refresh data if the deleted column had filters applied.
                self.data.refresh();
            }
            self.editColumnController.unset();
        };

        self.isSortableColumn = function (columnName) {
            if (!options.unsortableColumnNames) return true;
            return (options.unsortableColumnNames.indexOf(columnName) === -1);
        };

        self.toggleSortColumn = function (column) {
            if (column.sort() === 'asc') {
                column.sort('desc');
            } else if (column.sort() === 'desc') {
                column.sort('asc');
            } else {
                _.each(self.columns(), function (col) {
                    col.sort(undefined);
                });
                column.sort('asc');
            }
            self.data.refresh();
        };

        self.unsupportedTaskName = ko.observable();

        self.saveFilters = function () {
            self.unsupportedTaskName(gettext("Save Filters"));
        };

        self.exportData = function () {
            self.unsupportedTaskName(gettext("Export Data"));
        };

        $('#js-modal-unsupported-task').on('hide.bs.modal', function () {
            self.unsupportedTaskName(undefined);
        });

        return self;
    };

    return {
        datagridController: datagridController,
        dataModels: dataModels,
    };
});
