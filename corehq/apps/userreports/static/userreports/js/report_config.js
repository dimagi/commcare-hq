/* global _, $, COMMCAREHQ, django */
var reportBuilder = function () {
    var self = this;

    self.ReportColumn = function (column, parent) {
        var self = this;

        self._defaultAggregation = function () {
            return column["groupByOrAggregation"] || (self.isNonNumeric ? 'expand' : 'sum');
        };

        self.columnId = column["column_id"];
        self.name = column["name"];
        self.label = column["label"];
        self.isNonNumeric = column["is_non_numeric"];

        self.groupByOrAggregation = ko.observable(self._defaultAggregation());
        self.groupByOrAggregation.subscribe(function (newValue) {
            self._reorderSelectedColumns(newValue);
            parent.refreshPreview();
        });

        self.isGroupByColumn = ko.pureComputed(function () {
            return self.groupByOrAggregation() === "groupBy"
        });
        self._previousGroupBy = null;
        self.groupByOrAggregation.subscribe(function (oldValue) {
            self._previousGroupBy = oldValue;
        }, null, "beforeChange");


        self.aggregation = ko.pureComputed(function () {
            if (self.groupByOrAggregation() === 'groupBy') {
                return null;
            }
            return self.groupByOrAggregation();
        });

        self._reorderSelectedColumns = function (newValue) {
            var index = parent.selectedColumns.indexOf(self);
            var lookAhead = index;
            var oldValueWasGroupBy = self._previousGroupBy === "groupBy";

            if (newValue === "groupBy") {
                if (oldValueWasGroupBy === false) {
                    // Move group-by column before aggregated columns
                    while (lookAhead > 0 && !parent.selectedColumns()[lookAhead - 1].isGroupByColumn()) {
                        lookAhead--;
                    }
                }
            } else {
                if (oldValueWasGroupBy === true) {
                    // Move aggregated column after group-by columns
                    var end = parent.selectedColumns().length - 1;
                    while (lookAhead < end && parent.selectedColumns()[lookAhead + 1].isGroupByColumn()) {
                        lookAhead++;
                    }
                }
            }

            if (lookAhead !== index) {
                parent.selectedColumns.splice(index, 1);  // Remove self
                parent.selectedColumns.splice(lookAhead, 0, self);  // Insert self
            }
        };

        self.notifyButton = function () {
            parent.saveButton.fire('change');
        };

        self.serialize = function (reportAggEnabled) {
            return {
                "column_id": self.columnId,
                "name": self.name,
                "label": self.label,
                "is_non_numeric": self.isNonNumeric,
                "is_group_by_column": reportAggEnabled ? self.isGroupByColumn() : false,
                "aggregation": reportAggEnabled ? self.aggregation() : null,
            };
        };

        return self;
    };

    /**
     * ReportConfig is a view model for managing report configuration
     */
    self.ReportConfig = function (config) {
        var self = this;

        /**
         * Populate self.selectedColumns
         */
        self._initializeSelectedColumns = function() {
            // Start with just 5 indicators as an example if we aren't editing an existing report with columns
            var _selected_columns = config['initialColumns'] || self.columnOptions.slice(0, 5);
            self.selectedColumns(_.map(
                _selected_columns,
                function (column) {
                    return new reportBuilder.ReportColumn(column, self);
                }
            ));
        };

        self._mapboxAccessToken = config['mapboxAccessToken'];

        self._app = config['app'];
        self._sourceType = config['sourceType'];
        self._sourceId = config['sourceId'];

        self.existingReportId = config['existingReport'];

        self.columnOptions = config["columnOptions"];  // Columns that could be added to the report
        self.reportPreviewUrl = config["reportPreviewUrl"];  // Fetch the preview data asynchronously.


        self.selectedColumns = ko.observableArray();
        self._initializeSelectedColumns();
        self.selectedColumns.subscribe(function (newValue) {
            self.refreshPreview(newValue);
            self.saveButton.fire('change');
        });

        self.reportTypeListLabel = (config['sourceType'] === "case") ? "Case List" : "Form List";
        self.reportTypeAggLabel = (config['sourceType'] === "case") ? "Case Summary" : "Form Summary";
        self.reportType = ko.observable(config['existingReportType'] || 'list');
        self.reportType.subscribe(function (newValue) {
            var wasAggregationEnabled = self.isAggregationEnabled();
            self.isAggregationEnabled(newValue === "table");
            self.previewChart(newValue === "table" && self.selectedChart() !== "none");
            if (self.isAggregationEnabled() && !wasAggregationEnabled) {
                // Group by the first report column by default
                if (self.selectedColumns().length > 0) {
                    self.selectedColumns()[0].groupByOrAggregation("groupBy");
                }
            }
            self.refreshPreview();
            self.saveButton.fire('change');
        });

        self.isAggregationEnabled = ko.observable(self.reportType() === "table");

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

        /**
         * Convert the data source properties passed through the template
         * context into objects with the correct format for the select2 and
         * questionsSelect knockout bindings.
         * @param dataSourceIndicators
         * @private
         */
        var _getSelectableProperties = function (dataSourceIndicators) {
            var utils = hqImport('userreports/js/utils.js');
            if (self._optionsContainQuestions(dataSourceIndicators)) {
                return _.compact(_.map(
                    dataSourceIndicators, utils.convertDataSourcePropertyToQuestionsSelectFormat
                ));
            } else {
                return _.compact(_.map(
                    dataSourceIndicators, utils.convertDataSourcePropertyToSelect2Format
                ));
            }
        };

        /**
         * Return true if the given data source indicators contain question indicators (as opposed to just meta
         * properties or case properties)
         * @param dataSourceIndicators
         * @private
         */
        self._optionsContainQuestions = function (dataSourceIndicators) {
            return _.any(dataSourceIndicators, function (o) {
                return o.type === 'question';
            });
        };

        self.location_field = ko.observable(config['initialLocation']);
        self.location_field.subscribe(function () {
            self.refreshPreview(self.selectedColumns());
        });

        self.optionsContainQuestions = self._optionsContainQuestions(config['dataSourceProperties']);
        self.selectablePropertyOptions = _getSelectableProperties(config['dataSourceProperties']);

        var PropertyList = hqImport('userreports/js/builder_view_models.js').PropertyList;
        self.filterList = new PropertyList({
            hasFormatCol: self._sourceType === "case",
            hasCalculationCol: false,
            initialCols: config['initialUserFilters'],
            buttonText: 'Add User Filter',
            analyticsAction: 'Add User Filter',
            propertyHelpText: django.gettext('Choose the property you would like to add as a filter to this report.'),
            displayHelpText: django.gettext('Web users viewing the report will see this display text instead of the property name. Name your filter something easy for users to understand.'),
            formatHelpText: django.gettext('What type of property is this filter?<br/><br/><strong>Date</strong>: Select this if the property is a date.<br/><strong>Choice</strong>: Select this if the property is text or multiple choice.'),
            reportType: self.reportType(),
            propertyOptions: config['dataSourceProperties'],
            selectablePropertyOptions: self.selectablePropertyOptions,
        });
        self.filterList.serializedProperties.subscribe(function () {
            self.saveButton.fire("change");
        });
        self.defaultFilterList = new PropertyList({
            hasFormatCol: true,
            hasCalculationCol: false,
            hasDisplayCol: false,
            hasFilterValueCol: true,
            initialCols: config['initialDefaultFilters'],
            buttonText: 'Add Default Filter',
            analyticsAction: 'Add Default Filter',
            propertyHelpText: django.gettext('Choose the property you would like to add as a filter to this report.'),
            formatHelpText: django.gettext('What type of property is this filter?<br/><br/><strong>Date</strong>: Select this to filter the property by a date range.<br/><strong>Value</strong>: Select this to filter the property by a single value.'),
            filterValueHelpText: django.gettext('What value or date range must the property be equal to?'),
            reportType: self.reportType(),
            propertyOptions: config['dataSourceProperties'],
            selectablePropertyOptions: self.selectablePropertyOptions,
        });
        self.defaultFilterList.serializedProperties.subscribe(function () {
            self.saveButton.fire("change");
        });

        self.refreshPreview = function (columns) {
            columns = typeof columns !== "undefined" ? columns : self.selectedColumns();
            $('#preview').hide();
            if (columns.length === 0) {
                return;  // Nothing to do.
            }
            $.ajax({
                url: self.reportPreviewUrl,
                type: 'post',
                contentType: 'application/json; charset=utf-8',
                data: JSON.stringify({
                    'location_field': self.location_field(),
                    'columns': _.map(columns, function (c) { return c.serialize(self.isAggregationEnabled()); }),
                    'aggregate': self.isAggregationEnabled(),
                    'app': self._app,
                    'source_type': self._sourceType,
                    'source_id': self._sourceId,
                }),
                dataType: 'json',
                success: self.renderReportPreview,
            });
        };

        // true if a map is being displayed. This is different than reportType === "map", because this is
        // only true if the preview function returned a mapSpec.
        self.displayMapPreview = ko.observable(false);

        self.renderReportPreview = function (data) {
            self._renderTablePreview(data['table']);
            self._renderChartPreview(data['table']);
            self._renderMapPreview(data['map_config'], data["map_data"]);
        };

        self._renderMapPreview = function (mapSpec, mapData) {
            if (self.reportType() === "map" && mapSpec) {
                self.displayMapPreview(true);
                mapSpec.mapboxAccessToken = self._mapboxAccessToken;
                var render = hqImport('reports_core/js/maps.js').render;
                render(mapSpec, mapData.aaData, $("#map-preview-container"));
            } else {
                self.displayMapPreview(false);
            }
        };

        self._renderChartPreview = function (data) {
            var charts = hqImport('reports_core/js/charts.js');
            if (self.selectedChart() !== "none") {
                if (data) {
                    // data looks like headers, followed by rows of values
                    // aaData needs to be a list of dictionaries
                    var columnNames = _.map(self.selectedColumns(), function (c) { return c.name; });
                    // ^^^ That's not going to work with multiple "Count Per Choice" values, which expand
                    // TODO: Resolve selectedColumns vs. data[0]
                    var aaData = _.map(
                        data.slice(1), // skip the headers, iterate the rows of values
                        function (row) { return _.object(_.zip(columnNames, row)); }
                    );
                } else {
                    var aaData = [];
                }

                var aggColumns = _.filter(self.selectedColumns(), function (c) {
                    return self.isAggregationEnabled && !c.isGroupByColumn();
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
                            "title": null,  // Using the report title looks dumb in the UI; just leave it out.
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

        self._renderTablePreview = function (data) {
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
        };

        self.removeColumn = function (column) {
            self.selectedColumns.remove(column);
        };

        self.addColumn = function () {
            var column = _.find(self.columnOptions, function (c) {
                return c["name"] === self.newColumnName();
            });
            self.selectedColumns.push(new reportBuilder.ReportColumn(column, self));
            self.newColumnName('');
        };

        self.otherColumns = ko.computed(function () {
            var names = _.map(self.selectedColumns(), function (c) { return c.name; });
            return _.filter(self.columnOptions, function (c) {
                return !_.contains(names, c["name"]);
            });
        });

        self.moreColumns = ko.computed(function () {
            return self.otherColumns().length > 0;
        });

        self.validate = function () {
            var isValid = true;
            if (!self.filterList.validate()) {
                isValid = false;
                $("#userFilterAccordion").collapse('show');
            }
            if (!self.defaultFilterList.validate()) {
                isValid = false;
                $("#defaultFilterAccordion").collapse('show');
            }
            if (!isValid){
                alert('Invalid report configuration. Please fix the issues and try again.');
            }
            return isValid;
        };

        self.serialize = function () {
            return {
                "existing_report": self.existingReportId,
                "report_title": $('#report-title').val(), // From the inline-edit component
                "report_description": $('#report-description').val(),  // From the inline-edit component
                "report_type": self.reportType(),
                "aggregate": self.isAggregationEnabled(),
                "chart": self.selectedChart(),
                "columns": _.map(self.selectedColumns(), function (c) { return c.serialize(self.isAggregationEnabled()); }),
                "location_field": self.location_field(),  
                "default_filters": JSON.parse(self.defaultFilterList.serializedProperties()),
                "user_filters": JSON.parse(self.filterList.serializedProperties()),
            };
        };

        var button = COMMCAREHQ.SaveButton;
        if (config['existingReport']) {
            button = COMMCAREHQ.makeSaveButton({
                // The SAVE text is the only thing that distringuishes this from COMMCAREHQ.SaveButton
                SAVE: django.gettext("Update Report"),
                SAVING: django.gettext("Saving..."),
                SAVED: django.gettext("Saved"),
                RETRY: django.gettext("Try Again"),
                ERROR_SAVING: django.gettext("There was an error saving"),
            }, 'btn btn-success');
        }

        self.saveButton = button.init({
            unsavedMessage: "You have unsaved settings.",
            save: function () {
                var isValid = self.validate();
                if (isValid) {
                    self.saveButton.ajax({
                        url: window.location.href,  // POST here; keep URL params
                        type: "POST",
                        data: JSON.stringify(self.serialize()),
                        dataType: 'json',
                        success: function (data) {
                            self.existingReportId = data['report_id'];
                        },
                    });
                }
            },
        });
        self.saveButton.ui.appendTo($("#saveButtonHolder"));

        $("#btnSaveView").click(function () {
            var isValid = self.validate();
            if (isValid) {
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
            }
        });

        self.refreshPreview(self.selectedColumns());
        return self;
    };

    return self;

}();
