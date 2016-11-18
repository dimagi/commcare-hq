/* global _, $, COMMCAREHQ */
var reportBuilder = function () {
    var self = this;

    self.ReportColumn = function (column, parent) {
        var self = this;

        self.columnId = column["column_id"];
        self.name = column["name"];
        self.label = column["label"];
        self.isNumeric = column["is_numeric"];
        self.aggregation = column["is_numeric"] ? "simple": null;
        self.isGroupByColumn = false;

        self.groupByOrAggregation = ko.observable(self.aggregation);
        self.groupByOrAggregation.subscribe(function (newValue) {
            var index = parent.selectedColumns.indexOf(self);
            var lookAhead = index;

            if (newValue === "groupBy") {
                if (self.isGroupByColumn === false) {
                    // Move group-by column before aggregated columns
                    while (lookAhead > 0 && !parent.selectedColumns()[lookAhead - 1].isGroupByColumn) {
                        lookAhead--;
                    }
                }
                self.isGroupByColumn = true;
                self.aggregation = null;
            } else {
                if (self.isGroupByColumn === true) {
                    // Move aggregated column after group-by columns
                    var end = parent.selectedColumns().length - 1;
                    while (lookAhead < end && parent.selectedColumns()[lookAhead + 1].isGroupByColumn) {
                        lookAhead++;
                    }
                }
                self.isGroupByColumn = false;
                self.aggregation = newValue;
            }

            if (lookAhead !== index) {
                parent.selectedColumns.splice(index, 1);  // Remove self
                parent.selectedColumns.splice(lookAhead, 0, self);  // Insert self
            }
            parent.refreshPreview();
        });

        self.serialize = function () {
            return {
                "column_id": self.columnId,
                "name": self.name,
                "label": self.label,
                "is_numeric": self.isNumeric,
                "is_group_by_column": self.isGroupByColumn,
                "aggregation": self.aggregation,
            };
        };

        return self;
    };

    /**
     * ReportConfig is a view model for managing report configuration
     */
    self.ReportConfig = function (config) {
        var self = this;
        self.reportTitle = config["reportTitle"];
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
            self.saveButton.fire('change');
        });
        self.selectedColumns.extend({ rateLimit: 50 });

        self.reportTypeListLabel = (config['sourceType'] === "case") ? "Case List" : "Form List";
        self.reportTypeAggLabel = (config['sourceType'] === "case") ? "Case Summary" : "Form Summary";
        self.reportType = ko.observable('list');
        self.reportType.subscribe(function (newValue) {
            var wasAggregationEnabled = self.isAggregationEnabled();
            self.isAggregationEnabled(newValue === "agg");
            self.previewChart(newValue === "agg" && self.selectedChart() !== "none");
            if (self.isAggregationEnabled() && !wasAggregationEnabled) {
                // Group by the first report column by default
                if (self.selectedColumns().length > 0) {
                    self.selectedColumns()[0].groupByOrAggregation("groupBy");
                }
            }
            self.refreshPreview();
            self.saveButton.fire('change');
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
                    'columns': _.map(columns, function (c) { return c.serialize(); }),
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
                    return self.isAggregationEnabled && c.isNumeric && !c.isGroupByColumn;
                });
                var groupByNames = _.map(
                    _.filter(self.selectedColumns(), function (c) {
                        return c.isGroupByColumn === true;
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

        self.serialize = function () {
            return {
                "report_title": self.reportTitle,
                "report_description": "",  // TODO: self.reportDescription,
                "report_type": self.reportType(),
                "aggregate": self.isAggregationEnabled(),
                "chart": self.selectedChart(),
                "columns": _.map(self.selectedColumns(), function (c) { return c.serialize(); }),
                "default_filters": [],  // TODO: self.defaultFilters,
                "user_filters": [],  // TODO: self.userFilters,
            };
        };

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unsaved settings.",
            save: function () {
                self.saveButton.ajax({
                    url: window.location.href,  // POST here; keep URL params
                    type: "POST",
                    data: JSON.stringify(self.serialize()),
                    dataType: 'json',
                });
            }
        });
        self.saveButton.ui.appendTo($("#saveButtonHolder"));

        $("#btnSaveView").click(function () {
            $.ajax({
                url: window.location.href,
                type: "POST",
                data: JSON.stringify(self.serialize()),
                success: function (data) {
                    // Redirect to the newly-saved report
                    self.saveButton.setState('saved');
                    window.location.href = data['report_url'];
                },
                dataType: 'json',
            });
        });

        return self;
    };

    return self;

}();
