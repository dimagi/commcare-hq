
var ReportModule = (function () {

    function ReportConfig(report_id, display, availableReportIds, language) {
        var self = this;
        this.lang = language;
        this.fullDisplay = display || {};
        this.availableReportIds = availableReportIds;
        this.display = ko.observable(this.fullDisplay[this.lang]);
        this.reportId = ko.observable(report_id);
        this.toJSON = function () {
            self.fullDisplay[self.lang] = self.display();
            return {
                report_id: self.reportId(),
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
        self.reports = ko.observableArray([]);
        for (var i = 0; i < availableReports.length; i++) {
            self.reportTitles[availableReports[i].report_id] = availableReports[i].title;
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
            var report = new ReportConfig(options.report_id, options.header, self.availableReportIds, self.lang);
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

        // add exiting reports to UI
        for (i = 0; i < currentReports.length; i += 1) {
            var report = newReport(currentReports[i]);
            self.reports.push(report);
        }
    }

    return ReportModule;
}());
