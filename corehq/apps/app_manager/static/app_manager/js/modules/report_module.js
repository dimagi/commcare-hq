hqDefine('app_manager/js/modules/report_module', function () {
    var graphConfigModel = function (reportId, reportName, availableReportIds, reportCharts, graphConfigs,
        columnXpathTemplate, dataPathPlaceholders, lang, langs, changeSaveButton) {
        var self = {},
            columnTemplate = _.template(columnXpathTemplate);

        graphConfigs = graphConfigs || {};

        self.graphUiElements = {};
        var graphConfigurationUiElement = hqImport('app_manager/js/details/graph_config').graphConfigurationUiElement;
        for (var i = 0; i < availableReportIds.length; i++) {
            var currentReportId = availableReportIds[i];
            self.graphUiElements[currentReportId] = {};
            for (var j = 0; j < reportCharts[currentReportId].length; j++) {
                var currentChart = reportCharts[currentReportId][j];
                var graphConfig = graphConfigs[currentChart.chart_id] || {
                    graph_type: 'bar',
                    series: _.map(currentChart.y_axis_columns, function () { return {}; }),
                };

                // Add series placeholders
                _.each(currentChart.y_axis_columns, function (column, index) {
                    if (graphConfig.series[index]) {
                        var dataPathPlaceholder = dataPathPlaceholders && dataPathPlaceholders[currentReportId]
                            ? dataPathPlaceholders[currentReportId][currentChart.chart_id]
                            : "[path will be automatically generated]"
                        ;
                        _.extend(graphConfig.series[index], {
                            data_path_placeholder: dataPathPlaceholder,
                            x_placeholder: columnTemplate({ id: currentChart.x_axis_column }),
                            y_placeholder: columnTemplate({ id: column.column_id }),
                        });
                    }
                });

                var graphEl = graphConfigurationUiElement({
                    childCaseTypes: [],
                    fixtures: [],
                    lang: lang,
                    langs: langs,
                }, graphConfig);
                graphEl.setName(reportName);
                self.graphUiElements[currentReportId][currentChart.chart_id] = graphEl;

                graphEl.on("change", function () {
                    changeSaveButton();
                });
            }
        }

        self.name = ko.observable(reportName);
        self.name.subscribe(function (newValue) {
            _.each(self.graphUiElements, function (reportGraphElements) {
                _.each(reportGraphElements, function (uiElement) {
                    uiElement.setName(newValue);
                });
            });
        });

        self.currentGraphUiElements = ko.computed(function () {
            return self.graphUiElements[reportId()];
        });

        self.currentCharts = ko.computed(function () {
            return reportCharts[reportId()];
        });

        self.getCurrentGraphUiElement = function (chartId) {
            return self.currentGraphUiElements()[chartId];
        };

        self.toJSON = function () {
            var chartsToConfigs = {};
            var currentChartsToConfigs = self.currentGraphUiElements();
            _.each(currentChartsToConfigs, function (graphConfig, chartId) {
                chartsToConfigs[chartId] = graphConfig.val();
            });
            return chartsToConfigs;
        };

        return self;
    };

    /**
     * View-model for the filters of a mobile UCR.
     *
     * @param savedReportId - the id of the report, currently saved. Can be undefined for unsaved report.
     * @param selectedReportId - KO observable for the id of the currently selected report
     * @param filterValues - { slug : saved filter data } for each saved filter
     * @param reportFilters - { report id --> [ { slug: filter slug } for each filter in report ] for each report }
     * @param changeSaveButton - function that enables the "Save" button
     */
    var filterConfigModel = function (savedReportId, selectedReportId, filterValues, reportFilters, changeSaveButton) {
        var self = {};

        self.reportFilters = JSON.parse(JSON.stringify(reportFilters || {}));
        _.each(self.reportFilters, function (filtersInReport, id) {
            for (var i = 0; i < filtersInReport.length; i++) {
                var filter = filtersInReport[i];
                if (id === savedReportId && _.has(filterValues, filter.slug)) {
                    filter.selectedValue = filterValues[filter.slug];
                    filter.selectedValue.doc_type = ko.observable(filter.selectedValue.doc_type);
                } else {
                    filter.selectedValue = {
                        doc_type: ko.observable(null),
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
                    'ancestor_location_type_name',
                ];
                for (var filterFieldsIndex = 0; filterFieldsIndex < filterFields.length; filterFieldsIndex++) {
                    var startVal = filter.selectedValue[filterFields[filterFieldsIndex]];
                    if (startVal === 0) {
                        filter.selectedValue[filterFields[filterFieldsIndex]] = ko.observable(0);
                    } else {
                        filter.selectedValue[filterFields[filterFieldsIndex]] = ko.observable(startVal || '');
                    }
                }
                var initial = filter.selectedValue.value;
                if (initial) {
                    if (!_.isArray(initial)) {
                        initial = [initial];
                    }
                } else {
                    initial = [];
                }
                filter.selectedValue.value = ko.observableArray(initial);

                filter.dynamicFilterName = ko.computed(function () {
                    return selectedReportId() + '/' + filter.slug;
                });

                if (filter.choices !== undefined && filter.show_all) {
                    filter.choices.unshift({value: "_all", display: gettext("Show All")});
                }
            }
        });

        self.selectedFilterStructure = ko.computed(function () { // for the chosen report
            return self.reportFilters[selectedReportId()];
        });

        self.toJSON = function () {
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
                    _.each(docTypeToField, function (field, docType) {
                        if (filter.selectedValue.doc_type() === docType) {
                            _.each(field, function (value) {
                                selectedFilterValues[filter.slug][value] = filter.selectedValue[value]();
                            });
                        }
                    });
                    if (filter.selectedValue.doc_type() === 'StaticChoiceListFilter') {
                        selectedFilterValues[filter.slug].value = filter.selectedValue.value();
                    }
                }
            }
            return selectedFilterValues;
        };

        self.addSubscribersToSaveButton = function () {
            var addSubscriberToSaveButton = function (observable) {
                observable.subscribe(changeSaveButton);
            };
            _.each(self.reportFilters, function (filtersInReport) {
                for (var i = 0; i < filtersInReport.length; i++) {
                    var filter = filtersInReport[i];
                    _.each(filter.selectedValue, addSubscriberToSaveButton);
                }
            });
        };

        return self;
    };

    var reportConfigModel = function (reportId, display,
        localizedDescription, xpathDescription, useXpathDescription,
        showDataTable, syncDelay, reportSlug, uuid, availableReportIds,
        reportCharts, graphConfigs, columnXpathTemplate, dataPathPlaceholders,
        filterValues, reportFilters,
        language, languages, changeSaveButton) {
        var self = {};
        self.lang = language;
        self.fullDisplay = display || {};
        self.fullLocalizedDescription = localizedDescription || {};
        self.uuid = uuid;
        self.availableReportIds = availableReportIds;
        self.showCodes = ko.observable(false);

        self.reportId = ko.observable(reportId);
        self.display = ko.observable(self.fullDisplay[self.lang]);
        self.localizedDescription = ko.observable(self.fullLocalizedDescription[self.lang]);
        self.xpathDescription = ko.observable(xpathDescription);
        self.useXpathDescription = ko.observable(useXpathDescription);
        self.showDataTable = ko.observable(showDataTable);
        self.syncDelay = ko.observable(syncDelay);
        self.instanceId = ko.observable(reportSlug || uuid);

        self.reportId.subscribe(changeSaveButton);
        self.display.subscribe(changeSaveButton);
        self.localizedDescription.subscribe(changeSaveButton);
        self.xpathDescription.subscribe(changeSaveButton);
        self.useXpathDescription.subscribe(changeSaveButton);
        self.showDataTable.subscribe(changeSaveButton);
        self.syncDelay.subscribe(changeSaveButton);
        self.instanceId.subscribe(changeSaveButton);

        self.graphConfig = graphConfigModel(self.reportId, self.display(), availableReportIds, reportCharts,
            graphConfigs, columnXpathTemplate, dataPathPlaceholders,
            self.lang, languages, changeSaveButton);
        self.display.subscribe(function (newValue) {
            self.graphConfig.name(newValue);
        });
        self.filterConfig = filterConfigModel(reportId, self.reportId, filterValues, reportFilters, changeSaveButton);

        self.toggleCodes = function () {
            self.showCodes(!self.showCodes());
        };

        self.validateDisplay = ko.computed(function () {
            if (!self.display()) {
                return gettext("Display text is required");
            }
            return "";
        });

        self.toJSON = function () {
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
                // only pass instanceId if it was manually specified
                report_slug: (self.instanceId() && self.instanceId() !== self.uuid) ? self.instanceId() : null,
                uuid: self.uuid,
            };
        };

        return self;
    };

    var staticFilterDataModel = function (options) {
        var self = {};
        self.filterChoices = options.filterChoices;
        // support "unselected"
        self.filterChoices.unshift({slug: null, description: 'No filter'});
        self.autoFilterChoices = options.autoFilterChoices;
        self.dateRangeOptions = options.dateRangeOptions;
        self.dateOperators = ['=', '<', '<=', '>', '>=', 'between'];
        self.numericOperators = ['=', '!=', '<', '<=', '>', '>='];
        return self;
    };

    var reportModuleModel = function (options) {
        var self = {};
        var currentReports = options.currentReports || [];
        var availableReports = options.availableReports || [];
        var saveURL = options.saveURL;
        self.supportSyncDelay = !options.mobileUcrV1;
        self.supportCustomUcrSlug = !options.mobileUcrV1;
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
        self.reportContextTile = ko.observable(options.reportContextTile);
        self.reports = ko.observableArray([]);
        self.columnXpathTemplate = options.columnXpathTemplate || "";
        self.dataPathPlaceholders = options.dataPathPlaceholders || {};
        for (var i = 0; i < availableReports.length; i++) {
            var report = availableReports[i];
            var reportId = report.report_id;
            self.reportTitles[reportId] = report.title;
            self.reportDescriptions[reportId] = report.description;
            self.reportCharts[reportId] = report.charts;
            self.reportFilters[reportId] = report.filter_structure;
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

        self.saveButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
            unsavedMessage: gettext("You have unsaved changes in your report list module"),
            save: function () {

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
                        report_context_tile: JSON.stringify(self.reportContextTile()),
                        multimedia: JSON.stringify(self.multimedia()),
                    },
                });
            },
        });

        self.changeSaveButton = function () {
            self.saveButton.fire('change');
        };

        self.currentModuleName.subscribe(self.changeSaveButton);
        self.currentModuleFilter.subscribe(self.changeSaveButton);
        self.reportContextTile.subscribe(self.changeSaveButton);
        $(options.containerId + ' input').on('textchange', self.changeSaveButton);

        var newReport = function (options) {
            options = options || {};
            var report = reportConfigModel(
                options.report_id,
                options.header,
                options.localized_description,
                options.xpath_description,
                options.use_xpath_description,
                options.show_data_table,
                options.sync_delay,
                options.report_slug,
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
        };
        self.addReport = function () {
            self.reports.push(newReport());
        };
        self.removeReport = function (report) {
            self.reports.remove(report);
            self.changeSaveButton();
        };

        // add existing reports to UI
        for (i = 0; i < currentReports.length; i += 1) {
            self.reports.push(newReport(currentReports[i]));
        }

        var getInstanceIdsInThisModule = function () {
            return _.map(self.reports(), function (r) {return r.instanceId();});
        };

        // flag instance ids with uuids outside this module
        var uuidsByInstanceId = hqImport('hqwebapp/js/initial_page_data').get('uuids_by_instance_id'),
            uuidsInThisModule = _.pluck(self.reports(), 'uuid'),
            instanceIdsElsewhere = _.chain(uuidsByInstanceId)
                .pairs()
                .filter(function (idPair) { return _.difference(idPair[1], uuidsInThisModule).length; })
                .map(_.first)
                .value();

        self.validateSlug = function (instanceId) {
            var allInstanceIds = instanceIdsElsewhere.concat(getInstanceIdsInThisModule()),
                isDuplicate = _.filter(allInstanceIds, function (iid) {return iid === instanceId;})
                    .length > 1;
            if (isDuplicate) {
                return gettext("This code is used in multiple places.");
            }
            return "";
        };

        return self;
    };

    $(function () {
        var setupValidation = hqImport('app_manager/js/app_manager').setupValidation;
        setupValidation(hqImport('hqwebapp/js/initial_page_data').reverse('validate_module_for_build'));
    });

    return {
        reportModuleModel: reportModuleModel,
        staticFilterDataModel: staticFilterDataModel,
    };
});

ko.bindingHandlers.editGraph = {
    init: function (element, valueAccessor) {
        $(element).find(":first").replaceWith(valueAccessor().ui);
    },
};
