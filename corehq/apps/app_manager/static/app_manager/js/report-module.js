
var ReportModule = (function () {

    function ReportConfig(report_id, display, availableReportIds, language, filterValues, reportFilters) {
        var self = this;
        this.lang = language;
        this.fullDisplay = display || {};
        this.availableReportIds = availableReportIds;
        this.display = ko.observable(this.fullDisplay[this.lang]); // chosen in UI
        this.reportId = ko.observable(report_id); // chosen in UI
        this.filterValues = filterValues || {};  // this stores the saved filter values
        this.reportFilters = reportFilters || {};  // stores filter structure
        this.toJSON = function () {
            self.fullDisplay[self.lang] = self.display();
            var filters = {};
            for(var filter_slug in self.filterValues) {
                filters[filter_slug] = self.filterValues[filter_slug];
            }
            return {
                report_id: self.reportId(),
                header: self.fullDisplay,
                filters: filters
            };
        };
        this.filterStructure = ko.computed(function() { // for the chosen report
            return self.reportFilters[self.reportId()];
        });
    }
    function ReportModule(options) {
        var self = this;
        var currentReports = options.currentReports || []; // structure for all reports
        var availableReports = options.availableReports || []; // config data for app reports
        var saveURL = options.saveURL;
        self.lang = options.lang;
        self.moduleName = options.moduleName;
        self.currentModuleName = ko.observable(options.moduleName[self.lang]);
        self.reportTitles = {}; // all reports (titles)
        self.reportFilters = {}; // id -> filter structure (all reports, filters)
        self.reports = ko.observableArray([]);
        for (var i = 0; i < availableReports.length; i++) {
            self.reportTitles[availableReports[i].report_id] = availableReports[i].title;
        }
        for (var i = 0; i < availableReports.length; i++) {
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
            var report = new ReportConfig(options.report_id, options.header, self.availableReportIds, self.lang, options.filters, self.reportFilters);
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
