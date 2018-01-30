/* globals hqDefine _ */
hqDefine('app_manager/js/modules/report_module', function () {
    // TODO: Ideally the separator would be defined in one place. Right now it is
    //       also defined corehq.apps.userreports.reports.filters.CHOICE_DELIMITER
    var select2Separator = "\u001F";

    function GraphConfig(reportId, reportName, availableReportIds, reportCharts, graph_configs,
                         columnXpathTemplate, dataPathPlaceholders, lang, langs, changeSaveButton) {
        var self = this,
            columnTemplate = _.template(columnXpathTemplate);

        graph_configs = graph_configs || {};

        self.graphUiElements = {};
        var GraphConfigurationUiElement = hqImport('app_manager/js/details/graph_config').GraphConfigurationUiElement;
        for (var i = 0; i < availableReportIds.length; i++) {
            var currentReportId = availableReportIds[i];
            self.graphUiElements[currentReportId] = {};
            for (var j = 0; j < reportCharts[currentReportId].length; j++) {
                var currentChart = reportCharts[currentReportId][j];
                var graph_config = graph_configs[currentChart.chart_id] || {
                    graph_type: 'bar',
                    series: _.map(currentChart.y_axis_columns, function(c) { return {}; }),
                };

                // Add series placeholders
                _.each(currentChart.y_axis_columns, function(column, index) {
                    if (graph_config.series[index]) {
                        var dataPathPlaceholder = dataPathPlaceholders && dataPathPlaceholders[currentReportId]
                            ? dataPathPlaceholders[currentReportId][currentChart.chart_id]
                            : "[path will be automatically generated]"
                        ;
                        _.extend(graph_config.series[index], {
                            data_path_placeholder: dataPathPlaceholder,
                            x_placeholder: columnTemplate({ id: currentChart.x_axis_column }),
                            y_placeholder: columnTemplate({ id: column.column_id }),
                        });
                    }
                });

                var graph_el = new GraphConfigurationUiElement({
                    childCaseTypes: [],
                    fixtures: [],
                    lang: lang,
                    langs: langs,
                }, graph_config);
                graph_el.setName(reportName);
                self.graphUiElements[currentReportId][currentChart.chart_id] = graph_el;

                graph_el.on("change", function() {
                    changeSaveButton();
                });
            }
        }

        this.name = ko.observable(reportName);
        this.name.subscribe(function(newValue) {
            _.each(self.graphUiElements, function(reportGraphElements) {
                _.each(reportGraphElements, function(uiElement) {
                    uiElement.setName(newValue);
                });
            });
        });

        this.currentGraphUiElements = ko.computed(function() {
            return self.graphUiElements[reportId()];
        });

        this.currentCharts = ko.computed(function() {
            return reportCharts[reportId()];
        });

        this.getCurrentGraphUiElement = function(chart_id) {
            return self.currentGraphUiElements()[chart_id];
        };

        this.toJSON = function () {
            var chartsToConfigs = {};
            var currentChartsToConfigs = self.currentGraphUiElements();
            _.each(currentChartsToConfigs, function(graph_config, chart_id) {
                chartsToConfigs[chart_id] = graph_config.val();
            });
            return chartsToConfigs;
        };
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
                    filter.choices.unshift({value: "_all", display: gettext("Show All")});
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
                          showDataTable, syncDelay, uuid, availableReportIds,
                          reportCharts, graph_configs, columnXpathTemplate, dataPathPlaceholders,
                          filterValues, reportFilters,
                          language, languages, changeSaveButton) {
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
        this.showDataTable = ko.observable(showDataTable);
        this.syncDelay = ko.observable(syncDelay);

        this.reportId.subscribe(changeSaveButton);
        this.display.subscribe(changeSaveButton);
        this.localizedDescription.subscribe(changeSaveButton);
        this.xpathDescription.subscribe(changeSaveButton);
        this.useXpathDescription.subscribe(changeSaveButton);
        this.showDataTable.subscribe(changeSaveButton);
        this.syncDelay.subscribe(changeSaveButton);

        self.graphConfig = new GraphConfig(this.reportId, this.display(), availableReportIds, reportCharts,
                                           graph_configs, columnXpathTemplate, dataPathPlaceholders,
                                           this.lang, languages, changeSaveButton);
        this.display.subscribe(function(newValue) {
            self.graphConfig.name(newValue);
        });
        this.filterConfig = new FilterConfig(report_id, this.reportId, filterValues, reportFilters, changeSaveButton);

        this.toJSON = function () {
            self.fullDisplay[self.lang] = self.display();
            self.fullLocalizedDescription[self.lang] = self.localizedDescription() || "";
            return {
                report_id: self.reportId(),
                complete_graph_configs: self.graphConfig.toJSON(),
                filters: self.filterConfig.toJSON(),
                header: self.fullDisplay,
                localized_description: self.fullLocalizedDescription,
                xpath_description: self.xpathDescription(),
                use_xpath_description: self.useXpathDescription(),
                show_data_table: self.showDataTable(),
                sync_delay: self.syncDelay(),
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
        self.supportSyncDelay = options.supportSyncDelay;
        self.globalSyncDelay = options.globalSyncDelay;
        self.staticFilterData = options.staticFilterData;
        self.languages = options.languages;
        self.lang = options.lang;
        self.moduleName = options.moduleName;
        self.moduleFilter = options.moduleFilter || "";
        self.currentModuleName = ko.observable(options.moduleName[self.lang]);
        self.currentModuleFilter = ko.observable(self.moduleFilter);
        self.menuImage = options.menuImage;
        self.menuAudio = options.menuAudio;
        self.reportTitles = {};
        self.reportDescriptions = {};
        self.reportCharts = {};
        self.reportFilters = {};
        self.reports = ko.observableArray([]);
        self.columnXpathTemplate = options.columnXpathTemplate || "";
        self.dataPathPlaceholders = options.dataPathPlaceholders || {};
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

        self.saveButton = hqImport("hqwebapp/js/main").initSaveButton({
            unsavedMessage: gettext("You have unsaved changes in your report list module"),
            save: function () {
                // validate that all reports have valid data
                var reports = self.reports();
                for (var i = 0; i < reports.length; i++) {
                    if (!reports[i].reportId() || !reports[i].display()) {
                        alert(gettext('Reports must have all properties set!'));
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
                options.show_data_table,
                options.sync_delay,
                options.uuid,
                self.availableReportIds,
                self.reportCharts,
                options.complete_graph_configs,
                self.columnXpathTemplate,
                self.dataPathPlaceholders,
                options.filters,
                self.reportFilters,
                self.lang,
                self.languages,
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

    $(function () {
        var setupValidation = hqImport('app_manager/js/app_manager').setupValidation;
        setupValidation(hqImport('hqwebapp/js/initial_page_data').reverse('validate_module_for_build'));
    });

    return {
        ReportModule: ReportModule,
        StaticFilterData: StaticFilterData,
        select2Separator: select2Separator
    };
});

ko.bindingHandlers.editGraph = {
    init: function (element, valueAccessor) {
        $(element).find(":first").replaceWith(valueAccessor().ui);
    },
};
