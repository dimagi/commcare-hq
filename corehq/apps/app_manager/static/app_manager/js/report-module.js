
var ReportModule = (function () {

    function Config(dict) {
        var self = this;

        dict = dict || {};

        self.keyValuePairs = ko.observableArray();
        for (var key in dict) {
            self.keyValuePairs.push([ko.observable(key), ko.observable(dict[key])]);
        }

        self.addConfig = function() {
            self.keyValuePairs.push([ko.observable(), ko.observable()]);
        };
    }

    function GraphConfig(report_id, reportId, availableReportIds, reportCharts, graph_configs) {
        var self = this;

        graph_configs = graph_configs || {};

        this.graphConfigs = {};
        for (var i = 0; i < availableReportIds.length; i++) {
            var currentReportId = availableReportIds[i];
            self.graphConfigs[currentReportId] = {};
            for (var j = 0; j < reportCharts[currentReportId].length; j++) {
                var currentChart = reportCharts[currentReportId][j];
                var graph_config = graph_configs[currentChart.chart_id] || {};
                var series_configs = {};
                var chart_series = [];
                for(var k = 0; k < currentChart.y_axis_columns.length; k++) {
                    var series = currentChart.y_axis_columns[k];
                    chart_series.push(series);
                    series_configs[series] = new Config(
                        currentReportId == report_id ? (graph_config.series_configs || {})[series] || {} : {}
                    );
                }

                self.graphConfigs[currentReportId][currentChart.chart_id] = {
                    graph_type: ko.observable(currentReportId == report_id ? graph_config.graph_type || 'bar' : 'bar'),
                    series_configs: series_configs,
                    chart_series: chart_series,
                    config: new Config(
                        currentReportId == report_id ? graph_config.config || {} : {}
                    )
                };
            }
        }

        this.currentGraphConfigs = ko.computed(function() {
            return self.graphConfigs[reportId()];
        });

        this.currentCharts = ko.computed(function() {
            return reportCharts[reportId()];
        });

        this.getCurrentGraphConfig = function(chart_id) {
            return self.currentGraphConfigs()[chart_id] || {config: {keyValuePairs: []}};
        };

        this.toJSON = function () {
            function configToDict(config) {
                var dict = {};
                var keyValuePairs = config.keyValuePairs();
                for (var i = 0; i < keyValuePairs.length; i++) {
                    dict[keyValuePairs[i][0]()] = keyValuePairs[i][1]();
                }
                return dict;
            }

            var chartsToConfigs = {};
            var currentChartsToConfigs = self.currentGraphConfigs();
            _.each(currentChartsToConfigs, function(graph_config, chart_id) {
                chartsToConfigs[chart_id] = {
                    series_configs: {}
                };
                for (var series in graph_config.series_configs) {
                    chartsToConfigs[chart_id].series_configs[series] = configToDict(graph_config.series_configs[series]);
                }
                chartsToConfigs[chart_id].graph_type = graph_config.graph_type();
                chartsToConfigs[chart_id].config = configToDict(graph_config.config);
            });
            return chartsToConfigs;
        };

        this.allGraphTypes = ['bar', 'time', 'xy'];
    }

    function FilterConfig(report_id, reportId, filterValues, reportFilters) {
        var self = this;

        this.reportFilters = ko.observable(JSON.parse(JSON.stringify(reportFilters)) || {});
        for (var _id in this.reportFilters()) {
            for (var i = 0; i < this.reportFilters()[_id].length; i++) {
                var filter = this.reportFilters()[_id][i];
                if (_id == report_id && filterValues.hasOwnProperty(filter.slug)) {
                    filter.selectedValue = filterValues[filter.slug];
                    filter.selectedValue.doc_type = ko.observable(filter.selectedValue.doc_type);
                } else {
                    filter.selectedValue = {
                        doc_type: ko.observable(null)
                    };
                }
                filter.selectedValue.filter_type = ko.observable(filter.selectedValue.filter_type || '');
                filter.selectedValue.start_date = ko.observable(filter.selectedValue.start_date || '');
                filter.selectedValue.end_date = ko.observable(filter.selectedValue.end_date || '');
                filter.selectedValue.custom_data_property = ko.observable(filter.selectedValue.custom_data_property || '');
                filter.selectedValue.value = ko.observable(filter.selectedValue.value ? filter.selectedValue.value.join("\u001F") : '');
                filter.selectedValue.select_value = ko.observable(filter.selectedValue.select_value || '');

                filter.dynamicFilterName = ko.computed(function () {
                    return reportId() + '/' + filter.slug;
                });

                if(filter.choices != undefined && filter.show_all) {
                    filter.choices.unshift({value: "_all", display: "Show All"}); // TODO: translate
                }
            }
        }

        this.selectedFilterStructure = ko.computed(function () { // for the chosen report
            return self.reportFilters[reportId()];
        });

        this.toJSON = function () {
            var selectedFilterStructure = self.selectedFilterStructure();
            var selectedFilterValues = {};
            for (var i = 0; i < selectedFilterStructure.length; i++) {
                var filter = selectedFilterStructure[i];
                if (filter.selectedValue.doc_type()) {
                    selectedFilterValues[filter.slug] = {};
                    selectedFilterValues[filter.slug]['doc_type'] = filter.selectedValue.doc_type();
                    // Depending on doc_type, pull the correct observables' values
                    if (filter.selectedValue.doc_type() == 'AutoFilter') {
                        selectedFilterValues[filter.slug]['filter_type'] = filter.selectedValue.filter_type();
                    } else if (filter.selectedValue.doc_type() == 'StaticDatespanFilter') {
                        selectedFilterValues[filter.slug]['start_date'] = filter.selectedValue.start_date();
                        selectedFilterValues[filter.slug]['end_date'] = filter.selectedValue.end_date();
                    } else if (filter.selectedValue.doc_type() == 'CustomDataAutoFilter') {
                        selectedFilterValues[filter.slug]['custom_data_property'] = filter.selectedValue.custom_data_property();
                    } else if (filter.selectedValue.doc_type() == 'StaticChoiceListFilter') {
                        selectedFilterValues[filter.slug]['value'] = filter.selectedValue.value().split("\u001F");
                    } else if(filter.selectedValue.doc_type() == 'StaticChoiceFilter') {
                        selectedFilterValues[filter.slug]['select_value'] = filter.selectedValue.select_value();
                    }
                }
            }
            return selectedFilterValues;
        }

        // TODO - add user-friendly text
        this.filterDocTypes = [null, 'AutoFilter', 'StaticDatespanFilter', 'CustomDataAutoFilter', 'StaticChoiceListFilter', 'StaticChoiceFilter'];
        this.autoFilterTypes = ['case_sharing_group', 'location_id', 'username', 'user_id']
    }

    function ReportConfig(report_id, display, availableReportIds,
                          reportCharts, graph_configs,
                          filterValues, reportFilters,
                          language) {
        var self = this;
        this.lang = language;
        this.fullDisplay = display || {};
        this.availableReportIds = availableReportIds;
        this.display = ko.observable(this.fullDisplay[this.lang]);
        this.reportId = ko.observable(report_id);
        this.graphConfig = new GraphConfig(report_id, this.reportId, availableReportIds, reportCharts, graph_configs);
        this.filterConfig = new FilterConfig(report_id, this.reportId, filterValues, reportFilters);

        this.toJSON = function () {
            self.fullDisplay[self.lang] = self.display();
            return {
                report_id: self.reportId(),
                graph_configs: self.graphConfig.toJSON(),
                filters: self.filterConfig.toJSON(),
                header: self.fullDisplay
            };
        };
    }

    function ReportModule(options) {
        var self = this;
        var currentReports = options.currentReports || [];
        var availableReports = options.availableReports || [];
        var saveURL = options.saveURL;
        self.lang = options.lang;
        self.moduleName = options.moduleName;
        self.currentModuleName = ko.observable(options.moduleName[self.lang]);
        self.reportTitles = {};
        self.reportCharts = {};
        self.reportFilters = {};
        self.reports = ko.observableArray([]);
        for (var i = 0; i < availableReports.length; i++) {
            var report = availableReports[i];
            var report_id = report.report_id;
            self.reportTitles[report_id] = report.title;
            self.reportCharts[report_id] = report.charts;
            self.reportFilters[report_id] = report.filter_structure;
        }

        self.availableReportIds = _.map(options.availableReports, function (r) { return r.report_id; });

        self.defaultReportTitle = function (reportId) {
            return self.reportTitles[reportId];
        };

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unsaved changes in your report list module",
            save: function () {
                // validate that all reports have valid data
                var reports = self.reports();
                for (var i = 0; i < reports.length; i++) {
                    if (!reports[i].reportId() || !reports[i].display()) {
                        alert('Reports must have all properties set!');
                    }
                }
                self.moduleName[self.lang] = self.currentModuleName();
                self.saveButton.ajax({
                    url: saveURL,
                    type: 'post',
                    dataType: 'json',
                    data: {
                        name: JSON.stringify(self.moduleName),
                        reports: JSON.stringify(_.map(self.reports(), function (r) { return r.toJSON(); }))
                    }
                });
            }
        });

        var changeSaveButton = function () {
            self.saveButton.fire('change');
        };

        self.currentModuleName.subscribe(changeSaveButton);

        function newReport(options) {
            options = options || {};
            var report = new ReportConfig(
                options.report_id,
                options.header,
                self.availableReportIds,
                self.reportCharts,
                options.graph_configs,
                options.filters,
                self.reportFilters,
                self.lang
            );
            report.display.subscribe(changeSaveButton);
            report.reportId.subscribe(changeSaveButton);
            report.reportId.subscribe(function (reportId) {
                report.display(self.defaultReportTitle(reportId));
            });

            return report;
        }
        this.addReport = function () {
            self.reports.push(newReport());
        };
        this.removeReport = function (report) {
            self.reports.remove(report);
            changeSaveButton();
        };

        // add existing reports to UI
        for (i = 0; i < currentReports.length; i += 1) {
            var report = newReport(currentReports[i]);
            self.reports.push(report);
        }
    }

    return ReportModule;
}());
