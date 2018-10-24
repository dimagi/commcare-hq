hqDefine('export/js/download_export', function () {
    'use strict';

    /*var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get;
    var downloadExportsApp = window.angular.module('downloadExportsApp', ['hq.download_export']);
    downloadExportsApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
        djangoRMIProvider.configure(initial_page_data('djng_current_rmi'));
    }]);
    downloadExportsApp.constant('exportList', initial_page_data('export_list'));
    downloadExportsApp.constant('maxColumnSize', initial_page_data('max_column_size'));
    downloadExportsApp.constant('defaultDateRange', initial_page_data('default_date_range'));
    downloadExportsApp.constant('checkForMultimedia', initial_page_data('check_for_multimedia'));
    downloadExportsApp.constant('formElement', {
        progress: function () {
            return $('#download-progress-bar');
        },
        group: function () {
            return $('#id_group');
        },
        user_type: function () {
            return $('#id_user_types');
        },
    });*/

    // Model for the form to select date range, users, etc.
    var downloadFormModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['exportList', 'exportType', 'formOrCase', 'progressModel', 'prepareUrl', 'smsExport', 'userTypes']);

        var self = {};

        self.exportList = options.exportList;
        self.exportType = options.exportType;
        self.filterName = self.exportType === "form" ? "emw" : "case_list_filter";
        self.formOrCase = options.formOrCase;
        self.prepareUrl = options.prepareUrl;
        self.smsExport = options.smsExport;
        self.userTypes = options.userTypes;

        // Form data
        self.dateRange = ko.observable();
        self.emw = ko.observable();

        // UI flags
        self.preparingExport = ko.observable(false);
        self.prepareExportError = ko.observable('');
        self.preparingMultimediaExport = ko.observable(false);
        self.downloadInProgress = ko.observable(false);
        self.hasMultimedia = ko.observable(false);  // TODO

        self.defaultPrepareExportError = ko.computed(function () {
            return self.prepareExportError() === 'default';
        });

        self.disablePrepareExport = ko.computed(function () {
            // TODO
            //ng-disabled="(!!exportFiltersForm.$invalid || isFormInvalid()) && !preparingExport">
        });

        self.sendAnalytics = function () {
            _.each(self.userTypes, function (user_type) {
                hqImport('analytix/js/google').track.event("Download Export", 'Select "user type"', user_type); // TODO: test
            });
            var action = (self.exportList.length > 1) ? "Bulk" : "Regular";
            hqImport('analytix/js/google').track.event("Download Export", self.exportType, action);
            if (self.has_case_history_table) {
                _.each(self.exportList, function (export_) {
                    if (export_.has_case_history_table) {
                        hqImport('analytix/js/google').track.event("Download Case History Export", export_.domain, export_.export_id);
                    }
                });
            }
        };

        self.prepareExport = function () {
            self.emw(hqImport('reports/js/reports.util').urlSerialize($('form[name="exportFiltersForm"]')));
            self.prepareExportError('');
            self.preparingExport(true);

            var filterNamesAsString = $("form[name='exportFiltersForm']").find("input[name=" + self.filterName + "]").val();

            function getFilterNames() {
                return (filterNamesAsString ? filterNamesAsString.split(',') : []);
            }

            hqImport('analytix/js/kissmetrix').track.event("Clicked Prepare Export", {
                "Export type": self.exportList[0].export_type,
                "filters": _.map(
                    getFilterNames(),
                    function (item) {
                        var prefix = "t__";
                        if (item.substring(prefix.length) === prefix) {
                            return self.userTypes[item.substring(prefix.length)];
                        }
                        return item;
                    }
                ).join()});

            $.ajax({
                method: 'POST',
                url: self.prepareUrl,
                data: {
                    form_or_case: self.formOrCase,
                    sms_export: self.smsExport,
                    exports: JSON.stringify(self.exportList),
                    max_column_size: self._maxColumnSize,
                    form_data: JSON.stringify({
                        date_range: self.dateRange(),
                        emw: self.emw(),
                    }),
                },
                success: function (data) {
                    if (data.success) {
                        self.sendAnalytics();
                        self.preparingExport(false);
                        self.downloadInProgress(true);
                        // TODO
                        //exportDownloadService.startDownload(data.download_id, self.exportType);
                    } else {
                        self._handlePrepareError(data);
                    }
                },
                error: self._handlePrepareError,
            });
        };

        self._handlePrepareError = function (data) {
            if (data && data.error) {
                // The server returned an error message.
                self.prepareExportError(data.error);
            } else {
                self.prepareExportError("default");
            }
            self.preparingExport(false);
            self.preparingMultimediaExport(false);
        };

        return self;
    };

    $(function () {
        hqImport("reports/js/filters/main").init();

        var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
            exportList = initialPageData.get('export_list'),
            exportType = exportList[0].export_type;

        var progressModel = downloadProgressModel({
            exportType: exportType,
            emailUrl: initialPageData.reverse('add_export_email_request'),
            formOrCase: initialPageData.get('form_or_case'),
            pollUrl: initialPageData.reverse('poll_custom_export_download'),
        });

        $("#download-export-form").koApplyBindings(downloadFormModel({
            exportList: exportList,
            exportType: exportType,
            formOrCase: initialPageData.get('form_or_case'),
            userTypes: initialPageData.get('user_types'),
            download: download,
            prepareUrl: initialPageData.reverse('prepare_custom_export'),
            smsExport: initialPageData.get('sms_export'),
        }));
    });
});
