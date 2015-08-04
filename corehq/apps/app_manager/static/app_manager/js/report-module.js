
var ReportModule = (function () {

    function FilterConfig(report_id, reportId, filterValues, reportFilters, changeSaveButton) {
        var self = this;

        this.reportFilters = JSON.parse(JSON.stringify(reportFilters)) || {};
        for(var _id in this.reportFilters) {
            for(var i = 0; i < this.reportFilters[_id].length; i++) {
                // Get saved values for initial report, then make observables
                var filter = this.reportFilters[_id][i];
                if(_id == report_id && filterValues.hasOwnProperty(filter.slug)) {
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
                    'select_value'
                ];
                for(var filterFieldsIndex in filterFields) {
                    filter.selectedValue[filterFields[filterFieldsIndex]] = ko.observable(filter.selectedValue[filterFields[filterFieldsIndex]] || '');
                }
                filter.selectedValue.value = ko.observable(filter.selectedValue.value ? filter.selectedValue.value.join("\u001F") : '');

                filter.dynamicFilterName = ko.computed(function() {
                    return reportId() + '/' + filter.slug;
                });

                if(filter.choices !== undefined && filter.show_all) {
                    filter.choices.unshift({value: "_all", display: "Show All"}); // TODO: translate
                }
            }
        }

        this.selectedFilterStructure = ko.computed(function() { // for the chosen report
            return self.reportFilters[reportId()];
        });

        this.toJSON = function() {
            var selectedFilterStructure = self.selectedFilterStructure();
            var selectedFilterValues = {};
            for(var i = 0; i < selectedFilterStructure.length; i++) {
                var filter = selectedFilterStructure[i];
                if(filter.selectedValue.doc_type()) {
                    selectedFilterValues[filter.slug] = {};
                    selectedFilterValues[filter.slug].doc_type = filter.selectedValue.doc_type();
                    // Depending on doc_type, pull the correct observables' values
                    var docTypeToField = {
                        AutoFilter: 'filter_type',
                        CustomDataAutoFilter: 'custom_data_property',
                        StaticChoiceFilter: 'select_value',
                        StaticDatespanFilter: 'date_range'
                    };
                    for(var docType in docTypeToField) {
                        if(filter.selectedValue.doc_type() == docType) {
                            var field = docTypeToField[docType];
                            selectedFilterValues[filter.slug][field] = filter.selectedValue[field]();
                        }
                    }
                    if(filter.selectedValue.doc_type() == 'StaticChoiceListFilter') {
                        selectedFilterValues[filter.slug].value = filter.selectedValue.value().split("\u001F");
                    }
                }
            }
            return selectedFilterValues;
        };

        this.addSubscribersToSaveButton = function() {
            for(var _id in this.reportFilters) {
                for (var i = 0; i < this.reportFilters[_id].length; i++) {
                    var filter = this.reportFilters[_id][i];
                    for (var key in filter.selectedValue) {
                        filter.selectedValue[key].subscribe(changeSaveButton);
                    }
                }
            }
        };

        // TODO - add user-friendly text
        this.filterDocTypes = [null, 'AutoFilter', 'StaticDatespanFilter', 'CustomDataAutoFilter', 'StaticChoiceListFilter', 'StaticChoiceFilter'];
        this.autoFilterTypes = ['case_sharing_group', 'location_id', 'username', 'user_id'];
        this.date_range_options = ['last7', 'last30', 'lastmonth'];
    }

    function ReportConfig(report_id, display, availableReportIds, language, changeSaveButton, filterValues, reportFilters) {
        var self = this;
        this.lang = language;
        this.fullDisplay = display || {};
        this.availableReportIds = availableReportIds;
        this.display = ko.observable(this.fullDisplay[this.lang]);
        this.reportId = ko.observable(report_id);
        this.filterConfig = new FilterConfig(report_id, this.reportId, filterValues, reportFilters, changeSaveButton);

        this.toJSON = function () {
            self.fullDisplay[self.lang] = self.display();
            return {
                report_id: self.reportId(),
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
        self.reportFilters = {};
        self.reports = ko.observableArray([]);
        for (var i = 0; i < availableReports.length; i++) {
            self.reportTitles[availableReports[i].report_id] = availableReports[i].title;
            self.reportFilters[availableReports[i].report_id] = availableReports[i].filter_structure;
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
            var report = new ReportConfig(options.report_id, options.header, self.availableReportIds, self.lang, changeSaveButton, options.filters, self.reportFilters);
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
