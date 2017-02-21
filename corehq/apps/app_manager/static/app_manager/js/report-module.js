/* globals hqDefine _ */
hqDefine('app_manager/js/report-module.js', function () {
    // TODO: Ideally the separator would be defined in one place. Right now it is
    //       also defined corehq.apps.userreports.reports.filters.CHOICE_DELIMITER
    var select2Separator = "\u001F";

    function KeyValuePair(key, value, config) {
        var self = this;

        self.key = ko.observable(key);
        self.value = ko.observable(value);
        self.config = config;

        self.remove = function() {
            config.keyValuePairs.remove(self);
        };
    }

    function Config(dict) {
        var self = this;

        dict = dict || {};

        self.keyValuePairs = ko.observableArray();
        _.each(dict, function(value, key) {
            self.keyValuePairs.push(new KeyValuePair(key, value, self));
        });

        self.addConfig = function() {
            self.keyValuePairs.push(new KeyValuePair('', '', self));
        };
    }

    function GraphConfig(report_id, reportId, availableReportIds, reportCharts, graph_configs, changeSaveButton) {
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
                    var series = currentChart.y_axis_columns[k].column_id;
                    chart_series.push(series);
                    series_configs[series] = new Config(
                        currentReportId === report_id ? (graph_config.series_configs || {})[series] || {} : {}
                    );
                }

                self.graphConfigs[currentReportId][currentChart.chart_id] = {
                    graph_type: ko.observable(currentReportId === report_id ? graph_config.graph_type || 'bar' : 'bar'),
                    series_configs: series_configs,
                    chart_series: chart_series,
                    config: new Config(
                        currentReportId === report_id ? graph_config.config || {} : {}
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
                    dict[keyValuePairs[i].key()] = keyValuePairs[i].value();
                }
                return dict;
            }

            var chartsToConfigs = {};
            var currentChartsToConfigs = self.currentGraphConfigs();
            _.each(currentChartsToConfigs, function(graph_config, chart_id) {
                chartsToConfigs[chart_id] = {
                    series_configs: {}
                };
                _.each(graph_config.series_configs, function(series_config, series) {
                    chartsToConfigs[chart_id].series_configs[series] = configToDict(series_config);
                });
                chartsToConfigs[chart_id].graph_type = graph_config.graph_type();
                chartsToConfigs[chart_id].config = configToDict(graph_config.config);
            });
            return chartsToConfigs;
        };

        this.addSubscribersToSaveButton = function() {
            var addSubscriberToSaveButton = function(observable) {
                observable.subscribe(changeSaveButton);
            };
            var addConfigToSaveButton = function(config) {
                addSubscriberToSaveButton(config.keyValuePairs);
                _.each(config.keyValuePairs(), function(keyValuePair) {
                    addSubscriberToSaveButton(keyValuePair.key);
                    addSubscriberToSaveButton(keyValuePair.value);
                });
            };
            _.each(self.graphConfigs, function(reportGraphConfigs) {
                _.each(reportGraphConfigs, function(graphConfig) {
                    addSubscriberToSaveButton(graphConfig.graph_type);
                    addConfigToSaveButton(graphConfig.config);
                    _.each(graphConfig.series_configs, addConfigToSaveButton);
                });
            });
        };

        this.allGraphTypes = ['bar', 'time', 'xy'];
    }

    /**
     * View-model for the filters of a mobile UCR.
     *
     * @param savedReportId - the id of the report, currently saved. Can be undefined for unsaved report.
     * @param selectedReportId - KO observable for the id of the currently selected report
     * @param filterValues - { slug : saved filter data } for each saved filter
     * @param reportFilters - { report id --> [ { slug: filter slug } for each filter in report ] for each report }
     * @param changeSaveButton - function that enables the "Save" button
     */
    function FilterConfig(savedReportId, selectedReportId, filterValues, reportFilters, changeSaveButton) {
        var self = this;

        this.reportFilters = JSON.parse(JSON.stringify(reportFilters || {}));
        _.each(this.reportFilters, function(filtersInReport, id) {
            for (var i = 0; i < filtersInReport.length; i++) {
                var filter = filtersInReport[i];
                if (id === savedReportId && filterValues.hasOwnProperty(filter.slug)) {
                    filter.selectedValue = filterValues[filter.slug];
                    filter.selectedValue.doc_type = ko.observable(filter.selectedValue.doc_type);
                } else {
                    filter.selectedValue = {
                        doc_type: ko.observable(null)
                    };
                }
                var filterFields = [
                    'custom_data_property',
                    'date_range',
                    'filter_type',
                    'select_value',
                    'operator',
                    'operand',
                    'date_number',
                    'date_number2',
                    'start_of_month',
                    'period',
                    'ancestor_location_type_name'
                ];
                for(var filterFieldsIndex = 0; filterFieldsIndex < filterFields.length; filterFieldsIndex++) {
                    startVal = filter.selectedValue[filterFields[filterFieldsIndex]];
                    if (startVal === 0) {
                        filter.selectedValue[filterFields[filterFieldsIndex]] = ko.observable(0);
                    } else {
                        filter.selectedValue[filterFields[filterFieldsIndex]] = ko.observable(startVal || '');
                    }
                }
                filter.selectedValue.value = ko.observable(filter.selectedValue.value ? filter.selectedValue.value.join(select2Separator) : '');

                filter.dynamicFilterName = ko.computed(function () {
                    return selectedReportId() + '/' + filter.slug;
                });

                if(filter.choices !== undefined && filter.show_all) {
                    filter.choices.unshift({value: "_all", display: "Show All"}); // TODO: translate
                }
            }
        });

        this.selectedFilterStructure = ko.computed(function () { // for the chosen report
            return self.reportFilters[selectedReportId()];
        });

        this.toJSON = function () {
            var selectedFilterStructure = self.selectedFilterStructure();
            var selectedFilterValues = {};
            for (var i = 0; i < selectedFilterStructure.length; i++) {
                var filter = selectedFilterStructure[i];
                if (filter.selectedValue.doc_type()) {
                    selectedFilterValues[filter.slug] = {};
                    selectedFilterValues[filter.slug].doc_type = filter.selectedValue.doc_type();
                    // Depending on doc_type, pull the correct observables' values
                    var docTypeToField = {
                        AutoFilter: ['filter_type'],
                        CustomDataAutoFilter: ['custom_data_property'],
                        StaticChoiceFilter: ['select_value'],
                        StaticDatespanFilter: ['date_range'],
                        CustomDatespanFilter: ['operator', 'date_number', 'date_number2'],
                        CustomMonthFilter: ['start_of_month', 'period'],
                        AncestorLocationTypeFilter: ['ancestor_location_type_name'],
                        NumericFilter: ['operator', 'operand'],
                    };
                    _.each(docTypeToField, function(field, docType) {
                        if(filter.selectedValue.doc_type() === docType) {
                            _.each(field, function(value) {
                                selectedFilterValues[filter.slug][value] = filter.selectedValue[value]();
                            });
                        }
                    });
                    if(filter.selectedValue.doc_type() === 'StaticChoiceListFilter') {
                        selectedFilterValues[filter.slug].value = filter.selectedValue.value().split(select2Separator);
                    }
                }
            }
            return selectedFilterValues;
        };

        this.addSubscribersToSaveButton = function() {
            var addSubscriberToSaveButton = function(observable) {
                observable.subscribe(changeSaveButton);
            };
            _.each(this.reportFilters, function(filtersInReport) {
                for (var i = 0; i < filtersInReport.length; i++) {
                    var filter = filtersInReport[i];
                    _.each(filter.selectedValue, addSubscriberToSaveButton);
                }
            });
        };
    }

    function ReportConfig(report_id, display,
                          localizedDescription, xpathDescription, useXpathDescription,
                          uuid, availableReportIds,
                          reportCharts, graph_configs,
                          filterValues, reportFilters,
                          language, changeSaveButton) {
        var self = this;
        this.lang = language;
        this.fullDisplay = display || {};
        this.fullLocalizedDescription = localizedDescription || {};
        this.uuid = uuid;
        this.availableReportIds = availableReportIds;

        this.reportId = ko.observable(report_id);
        this.display = ko.observable(this.fullDisplay[this.lang]);
        this.localizedDescription = ko.observable(this.fullLocalizedDescription[this.lang]);
        this.xpathDescription = ko.observable(xpathDescription);
        this.useXpathDescription = ko.observable(useXpathDescription);

        this.reportId.subscribe(changeSaveButton);
        this.display.subscribe(changeSaveButton);
        this.localizedDescription.subscribe(changeSaveButton);
        this.xpathDescription.subscribe(changeSaveButton);
        this.useXpathDescription.subscribe(changeSaveButton);

        this.graphConfig = new GraphConfig(report_id, this.reportId, availableReportIds, reportCharts, graph_configs, changeSaveButton);
        this.filterConfig = new FilterConfig(report_id, this.reportId, filterValues, reportFilters, changeSaveButton);

        this.toJSON = function () {
            self.fullDisplay[self.lang] = self.display();
            self.fullLocalizedDescription[self.lang] = self.localizedDescription() || "";
            return {
                report_id: self.reportId(),
                graph_configs: self.graphConfig.toJSON(),
                filters: self.filterConfig.toJSON(),
                header: self.fullDisplay,
                localized_description: self.fullLocalizedDescription,
                xpath_description: self.xpathDescription(),
                use_xpath_description: self.useXpathDescription(),
                uuid: self.uuid,
            };
        };
    }

    function StaticFilterData(options) {
        this.filterChoices = options.filterChoices;
        // support "unselected"
        this.filterChoices.unshift({slug: null, description: 'No filter'});
        this.autoFilterChoices = options.autoFilterChoices;
        this.dateRangeOptions = options.dateRangeOptions;
        this.dateOperators = ['=', '<', '<=', '>', '>=', 'between'];
        this.numericOperators = ['=', '!=', '<', '<=', '>', '>='];
    }

    function ReportModule(options) {
        var self = this;
        var currentReports = options.currentReports || [];
        var availableReports = options.availableReports || [];
        var saveURL = options.saveURL;
        self.staticFilterData = options.staticFilterData;
        self.lang = options.lang;
        self.moduleName = options.moduleName;
        self.moduleFilter = options.moduleFilter === "None" ? "" : options.moduleFilter;
        self.currentModuleName = ko.observable(options.moduleName[self.lang]);
        self.currentModuleFilter = ko.observable(self.moduleFilter);
        self.menuImage = options.menuImage;
        self.menuAudio = options.menuAudio;
        self.reportTitles = {};
        self.reportDescriptions = {};
        self.reportCharts = {};
        self.reportFilters = {};
        self.reports = ko.observableArray([]);
        for (var i = 0; i < availableReports.length; i++) {
            var report = availableReports[i];
            var report_id = report.report_id;
            self.reportTitles[report_id] = report.title;
            self.reportDescriptions[report_id] = report.description;
            self.reportCharts[report_id] = report.charts;
            self.reportFilters[report_id] = report.filter_structure;
        }

        self.availableReportIds = _.map(options.availableReports, function (r) { return r.report_id; });

        self.defaultReportTitle = function (reportId) {
            return self.reportTitles[reportId];
        };
        self.defaultReportDescription = function (reportId) {
            return self.reportDescriptions[reportId];
        };

        self.multimedia = function () {
            var multimedia = {};
            multimedia.mediaImage = {};
            multimedia.mediaImage[self.lang] = self.menuImage.savedPath();
            multimedia.mediaAudio = {};
            multimedia.mediaAudio[self.lang] = self.menuAudio.savedPath();
            return multimedia;
        };

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unsaved changes in your report list module",
            save: function () {
                // validate that all reports have valid data
                var reports = self.reports();
                for (var i = 0; i < reports.length; i++) {
                    if (!reports[i].reportId() || !reports[i].display()) {
                        alert('Reports must have all properties set!');
                        break;
                    }
                }
                self.moduleName[self.lang] = self.currentModuleName();

                var filter = self.currentModuleFilter().trim();
                self.moduleFilter = filter === '' ? undefined : filter;

                self.saveButton.ajax({
                    url: saveURL,
                    type: 'post',
                    dataType: 'json',
                    data: {
                        name: JSON.stringify(self.moduleName),
                        module_filter: self.moduleFilter,
                        reports: JSON.stringify(_.map(self.reports(), function (r) { return r.toJSON(); })),
                        multimedia: JSON.stringify(self.multimedia())
                    }
                });
            }
        });

        self.changeSaveButton = function () {
            self.saveButton.fire('change');
        };

        self.currentModuleName.subscribe(self.changeSaveButton);
        self.currentModuleFilter.subscribe(self.changeSaveButton);
        $(options.containerId + ' input').on('textchange', self.changeSaveButton);

        function newReport(options) {
            options = options || {};
            var report = new ReportConfig(
                options.report_id,
                options.header,
                options.localized_description,
                options.xpath_description,
                options.use_xpath_description,
                options.uuid,
                self.availableReportIds,
                self.reportCharts,
                options.graph_configs,
                options.filters,
                self.reportFilters,
                self.lang,
                self.changeSaveButton
            );
            report.reportId.subscribe(function (reportId) {
                report.display(self.defaultReportTitle(reportId));
            });
            report.reportId.subscribe(function (reportId) {
                report.localizedDescription(self.defaultReportDescription(reportId));
            });

            return report;
        }
        this.addReport = function () {
            self.reports.push(newReport());
        };
        this.removeReport = function (report) {
            self.reports.remove(report);
            self.changeSaveButton();
        };

        // add existing reports to UI
        for (i = 0; i < currentReports.length; i += 1) {
            var report = newReport(currentReports[i]);
            self.reports.push(report);
        }
    }
    return {
        ReportModule: ReportModule,
        StaticFilterData: StaticFilterData,
        select2Separator: select2Separator
    };
});
