/* global _, $ */
var reportBuilder = function () {
    var self = this;

    self.ReportColumn = function (column, parent) {
        var self = this;

        self.columnId = column["column_id"];
        self.name = column["name"];
        self.label = column["label"];
        self.isNumeric = column["is_numeric"];
        self.aggregation = ko.observable(column["is_numeric"] ? "sum": null);
        self.isFormatEnabled = ko.observable(false);
        self.isGroupByColumn = ko.observable(false);
        self.aggregation.subscribe(function (newValue) {
            parent.refreshPreview();
        });

        return self;
    };

    /**
     * ReportConfig is a view model for managing report configuration
     */
    self.ReportConfig = function (config) {
        var self = this;
        self.columns = config["columns"];
        self.dataSourceUrl = config["dataSourceUrl"];  // Fetch the preview data asynchronously.

        self.selectedColumns = ko.observableArray(_.map(
            self.columns.slice(0, 5),  // Start with just 5 indicators.
            function (column) {
                return new reportBuilder.ReportColumn(column, self);
            }
        ));
        self.selectedColumns.subscribe(function (newValue) {
            self.refreshPreview(newValue);
        });
        self.selectedColumns.extend({ rateLimit: 50 });

        if (config['sourceType'] === "case") {
            self.reportTypeOptions = [
                {"name": "list", "label": "Case List"},
                {"name": "agg", "label": "Case Summary"},
                {"name": "map", "label": "Map"},
            ];
        } else {
            self.reportTypeOptions = [
                {"name": "list", "label": "Form List"},
                {"name": "agg", "label": "Form Summary"},
                {"name": "map", "label": "Map"},
            ];
        }
        self.reportType = ko.observable('list');
        self.reportType.subscribe(function (newValue) {
            var wasGroupByEnabled = self.isGroupByEnabled();
            self.isGroupByEnabled(newValue === "agg");
            self.previewChart(newValue === "agg" && self.selectedChart() !== "none");
            if (self.isGroupByEnabled() && !wasGroupByEnabled) {
                // Group by the first report column by default
                var firstColumn = self.selectedColumns().length > 0 ? self.selectedColumns()[0] : self.columns[0];
                self.selectedGroupByName(firstColumn.name);
            }
            self.setIsFormatEnabled();
            self.refreshPreview();
        });

        self.isGroupByEnabled = ko.observable(false);
        self.groupByHeading = ko.observable("Group By");
        self.groupByColumnStatus = ko.observable("Grouped By");
        self.selectedGroupByName = ko.observable();
        self.selectedGroupByName.subscribe(function (newValue) {
            if (newValue) {  // Check whether it has a value, because the user can unselect group by
                // Put the group-by column first in the report
                var selectedColumnNames = _.map(self.selectedColumns(), function (c) { return c.name; });
                var index = selectedColumnNames.indexOf(newValue);
                var column;
                if (index === -1) {
                    // The column is not in the report. Insert it.
                    column = _.find(self.columns, function (c) { return c["name"] === newValue; });
                    self.selectedColumns.unshift(new reportBuilder.ReportColumn(column, self));
                } else if (index > 0) {
                    // The column is already in the report, but not first. Bump it up.
                    column = self.selectedColumns.splice(index, 1)[0];
                    self.selectedColumns.unshift(column);
                }
            }
            self.setIsFormatEnabled();
            self.refreshPreview();
        });

        self.isFormatEnabled = ko.observable(false);
        self.setIsFormatEnabled = function () {
            var isFormatEnabled = self.isGroupByEnabled() && self.selectedGroupByName();
            self.isFormatEnabled(isFormatEnabled);
            // enable "Format" dropdown for each column that is not the group-by column.
            _.each(self.selectedColumns(), function (column) {
                column.isFormatEnabled(isFormatEnabled && column.name !== self.selectedGroupByName());
                column.isGroupByColumn(isFormatEnabled && column.name === self.selectedGroupByName());
            });
        };

        self.newColumnName = ko.observable('');

        self.selectedChart = ko.observable('none');
        self.selectedChart.subscribe(function (newValue) {
            if (newValue === "none") {
                self.groupByHeading("Group By");
                self.groupByColumnStatus("Grouped By");
                self.previewChart(false);
            } else {
                self.groupByHeading("Categories");
                self.groupByColumnStatus("Category");
                self.previewChart(true);
                self.refreshPreview();
            }
        });

        self.previewChart = ko.observable(false);

        self.sum = function (array) {
            var sum = 0;
            try {
                _.each(array, function (x) {
                    if (!_.isNumber(x)) {
                        throw new TypeError('"' + x + '" is not a number.');
                    }
                    sum += x;
                });
            } catch (err) {
                return "---";
            }
            return sum;
        };

        self.avg = function (array) {
            var sum = self.sum(array);
            if (_.isNumber(sum)) {
                return sum / array.length;
            } else {
                return "---";
            }
        };

        self.count = function (array) {
            return array.length;
        };

        self.refreshPreview = function (columns) {
            columns = typeof columns !== "undefined" ? columns : self.selectedColumns();
            $('#preview').hide();
            if (columns.length === 0) {
                return;  // Nothing to do.
            }
            $.ajax({
                url: self.dataSourceUrl,
                type: 'post',
                contentType: 'application/json; charset=utf-8',
                data: JSON.stringify({'columns': columns, 'aggregate': self.isFormatEnabled()}),
                dataType: 'json',
                success: self.renderChart,
            });
        };

        self.renderChart = function (data) {
            var charts = hqImport('reports_core/js/charts.js');

            if (self.dataTable) {
                self.dataTable.destroy();
            }
            $('#preview').empty();
            self.dataTable = $('#preview').DataTable({
                "autoWidth": false,
                "ordering": false,
                "paging": false,
                "searching": false,
                "columns": _.map(data[0], function(column) { return {"title": column}; }),
                "data": data.slice(1),
            });
            $('#preview').show();

            if (self.selectedChart() !== "none") {
                var aaData = data;

                var aggColumns = _.filter(self.selectedColumns(), function (c) {
                    return c.isFormatEnabled() && c.isNumeric;
                });
                var categoryNames = _.map(
                    _.filter(self.selectedColumns(), function (c) { return c.isFormatEnabled() === false; }),
                    function (c) { return c.name; }
                );
                if (aggColumns.length > 0 && categoryNames.length > 0) {
                    var chartSpecs;
                    if (self.selectedChart() === "bar") {
                        var aggColumnsSpec = _.map(aggColumns, function (c) {
                            return {"display": c.label, "column_id": c.name};
                        });
                        chartSpecs = [{
                            "type": "multibar",
                            "chart_id": "5221328456932991781",
                            "title": null,
                            "y_axis_columns": aggColumnsSpec,
                            "x_axis_column": categoryNames[0],
                            "is_stacked": false,
                            "aggregation_column": null,
                        }];
                    } else {
                        // pie
                        chartSpecs = [{
                            "type": "pie",
                            "chart_id": "-6021326752156782988",
                            "title": null,
                            "value_column": aggColumns[0].name,
                            "aggregation_column": categoryNames[0],
                        }];
                    }
                    charts.render(chartSpecs, aaData, $('#chart'));
                }
            }
        };

        self.removeColumn = function (column) {
            self.selectedColumns.remove(column);
        };

        self.addColumn = function () {
            var column = _.find(self.columns, function (c) {
                return c["name"] === self.newColumnName();
            });
            self.selectedColumns.push(new reportBuilder.ReportColumn(column, self));
            self.setIsFormatEnabled();
            self.newColumnName('');
        };

        self.otherColumns = ko.computed(function () {
            var names = _.map(self.selectedColumns(), function (c) { return c.name; });
            return _.filter(self.columns, function (c) {
                return !_.contains(names, c["name"]);
            });
        });

        self.moreColumns = ko.computed(function () {
            return self.otherColumns().length > 0;
        });

        return self;
    };

    return self;

}();
