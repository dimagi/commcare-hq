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
        self.isGroupByColumn = ko.observable(false);
        self.isGroupByColumn.subscribe(function (newValue) {
            var index = parent.selectedColumns.indexOf(self);
            var lookAhead = index;
            if (newValue) {
                // Move group-by column before aggregated columns
                while (lookAhead > 0 && !parent.selectedColumns()[lookAhead - 1].isGroupByColumn()) {
                    lookAhead--;
                }
            } else {
                // Move aggregated column after group-by columns
                var end = parent.selectedColumns().length - 1;
                while (lookAhead < end && parent.selectedColumns()[lookAhead + 1].isGroupByColumn()) {
                    lookAhead++;
                }
            }
            if (lookAhead !== index) {
                parent.selectedColumns.splice(index, 1);  // Remove self
                parent.selectedColumns.splice(lookAhead, 0, self);  // Insert self
            }
            parent.refreshPreview();
        });
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
            var wasAggregationEnabled = self.isAggregationEnabled();
            self.isAggregationEnabled(newValue === "agg");
            self.previewChart(newValue === "agg" && self.selectedChart() !== "none");
            if (self.isAggregationEnabled() && !wasAggregationEnabled) {
                // Group by the first report column by default
                if (self.selectedColumns().length > 0) {
                    self.selectedColumns()[0].isGroupByColumn(true);
                }
            }
            self.refreshPreview();
        });

        self.isAggregationEnabled = ko.observable(false);

        self.newColumnName = ko.observable('');

        self.selectedChart = ko.observable('none');
        self.selectedChart.subscribe(function (newValue) {
            if (newValue === "none") {
                self.previewChart(false);
            } else {
                self.previewChart(true);
                self.refreshPreview();
            }
        });

        self.previewChart = ko.observable(false);

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
                data: JSON.stringify({
                    'columns': _.map(columns, function (c) { return {
                        'columnId': c.columnId,
                        'name': c.name,
                        'label': c.label,
                        'isNumeric': c.isNumeric,
                        'isGroupByColumn': c.isGroupByColumn(),
                        'aggregation': c.aggregation(),
                    }; }),
                    'aggregate': self.isAggregationEnabled(),
                }),
                dataType: 'json',
                success: self.renderReportPreview,
            });
        };

        self.renderReportPreview = function (data) {
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
                    return self.isAggregationEnabled && c.isNumeric && !c.isGroupByColumn();
                });
                var groupByNames = _.map(
                    _.filter(self.selectedColumns(), function (c) {
                        return c.isGroupByColumn() === true;
                    }),
                    function (c) { return c.name; }
                );
                if (aggColumns.length > 0 && groupByNames.length > 0) {
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
                            "x_axis_column": groupByNames[0],
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
                            "aggregation_column": groupByNames[0],
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
