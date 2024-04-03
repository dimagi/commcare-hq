/**
 *  UI for the page to download an export (form, case, or SMS; single or bulk).
 *
 *  Contains two models:
 *      downloadFormModel: Controls the form where the user specifies a date range, etc. Also contains
 *          functionality to download the multimedia associated with an export (form exports only).
 *      downloadProgressModel: Controls the progress bar, etc. once the user has clicked 'Prepare Export'.
 *          Includes functionality to email the user when the export is done, rather than them waiting for it.
 */
hqDefine('export/js/download_export', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'analytix/js/google',
    'analytix/js/kissmetrix',
    'reports/js/filters/bootstrap3/main',
    'reports/js/reports.util',
    'export/js/utils',
    'hqwebapp/js/daterangepicker.config',   // createDateRangePicker
    'jquery.cookie/jquery.cookie',      // for resuming export downloads on refresh
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData,
    googleAnalytics,
    kissmetricsAnalytics,
    reportFilters,
    reportUtils,
    exportUtils
) {
    'use strict';

    var downloadFormModel = function (options) {
        assertProperties.assert(options, [
            'defaultDateRange',
            'exportList',
            'exportType',
            'formOrCase',
            'maxColumnSize',
            'multimediaUrl',    // present if we should check for multimedia
            'progressModel',
            'prepareUrl',
            'prepareMultimediaUrl',
            'smsExport',
            'userTypes',
        ]);

        var self = _.extend({}, options);

        // Form data
        self.dateRange = ko.observable(self.defaultDateRange);
        self.getEMW = function () {
            // "expanded mobile worker" => the users (for forms) or case owners (for cases)
            return reportUtils.urlSerialize($('form[name="exportFiltersForm"]'));
        };

        // Cookie Related
        self.savedDownloadCookieName = _.map(self.exportList, function (exportData) {
            return exportData.export_id;
        }).join('.') + '_download';
        self.savedMultimediaDownloadCookieName = self.savedDownloadCookieName + '_multimedia';
        self.savedDownloadId = $.cookie(self.savedDownloadCookieName);
        self.savedMultimediaDownloadId = $.cookie(self.savedMultimediaDownloadCookieName);
        self.canResumeDownload = !!self.savedDownloadId;
        self.canResumeMultimediaDownload = !!self.savedMultimediaDownloadId;

        // UI flags
        self.preparingExport = ko.observable(false);
        self.prepareExportError = ko.observable('');
        self.preparingMultimediaExport = ko.observable(false);
        self.hasMultimedia = ko.observable(false);

        // Once the download starts, this (downloadFormModel) disables the form and displays a message.
        // When the download is complete, the downloadProgressModel gives the user the option to clear
        // filters and do another download. Listen for that signal.
        self.downloadInProgress = ko.observable(self.canResumeDownload || self.canResumeMultimediaDownload);

        // This resumes any refreshed / aborted downloads if cookies are present
        if (self.canResumeDownload) {
            self.progressModel.downloadCookieName(self.savedDownloadCookieName);
            self.progressModel.startDownload(self.savedDownloadId);
        } else if (self.canResumeMultimediaDownload) {
            self.progressModel.downloadCookieName(self.savedMultimediaDownloadCookieName);
            self.progressModel.startMultimediaDownload(self.savedMultimediaDownloadId);
        }

        self.progressModel.showDownloadStatus.subscribe(function (newValue) {
            self.downloadInProgress(newValue);
        });

        self.isValid = ko.computed(function () {
            return !!self.dateRange();
        });

        self.disablePrepareExport = ko.computed(function () {
            return !self.isValid() || self.preparingExport();
        });
        self.disablePrepareMultimediaExport = ko.computed(function () {
            return !self.isValid() || self.preparingMultimediaExport();
        });

        // Determine whether or not to show button to download multimedia
        if (self.multimediaUrl) {
            $.ajax({
                method: 'GET',
                url: self.multimediaUrl,
                data: {
                    export_id: self.exportList[0].export_id,
                    form_or_case: self.formOrCase,
                },
                success: function (data) {
                    if (data.success) {
                        self.hasMultimedia(data.hasMultimedia);
                    }
                },
            });
        }

        self.sendAnalytics = function () {
            var action = (self.exportList.length > 1) ? "Bulk" : "Regular";
            googleAnalytics.track.event("Download Export", self.exportType, action);
            _.each(self.exportList, function (export_) {
                if (export_.has_case_history_table) {
                    googleAnalytics.track.event("Download Case History Export", export_.domain, export_.export_id);
                }
            });
        };

        self.prepareExport = function () {
            self.prepareExportError('');
            self.preparingExport(true);

            // Generate human-readable list of mobile workers, to send to analytics
            function getFilterString() {
                var filterName = self.exportType === "form" ? "emw" : "case_list_filter",
                    filterNamesAsString = $("form[name='exportFiltersForm']").find("input[name=" + filterName + "]").val(),
                    filterNamesAsArray = filterNamesAsString ? filterNamesAsString.split(',') : [];
                return _.map(filterNamesAsArray, function (item) {
                    var prefix = "t__";
                    if (item.substring(0, prefix.length) === prefix) {
                        return self.userTypes[item.substring(prefix.length)];
                    }
                    return item;
                }).join();
            }

            kissmetricsAnalytics.track.event("Clicked Prepare Export", {
                "Export type": self.exportType,
                "filters": getFilterString(),
            });

            $.ajax({
                method: 'POST',
                url: self.prepareUrl,
                data: {
                    form_or_case: self.formOrCase,
                    sms_export: self.smsExport,
                    exports: JSON.stringify(self.exportList),
                    max_column_size: self.maxColumnSize,
                    form_data: JSON.stringify({
                        date_range: self.dateRange(),
                        emw: self.getEMW(),
                    }),
                },
                success: function (data) {
                    if (data.success) {
                        self.sendAnalytics();
                        self.preparingExport(false);
                        self.downloadInProgress(true);
                        self.progressModel.downloadCookieName(self.savedDownloadCookieName);
                        self.progressModel.startDownload(data.download_id);
                    } else {
                        self.handleError(data);
                    }
                },
                error: self.handleError,
            });
        };

        self.prepareMultimediaExport = function () {
            self.prepareExportError('');
            self.preparingMultimediaExport(true);
            $.ajax({
                method: 'POST',
                url: self.prepareMultimediaUrl,
                data: {
                    form_or_case: self.formOrCase,
                    sms_export: self.smsExport,
                    exports: JSON.stringify(self.exportList),
                    form_data: JSON.stringify({
                        date_range: self.dateRange(),
                        emw: self.getEMW(),
                    }),
                },
                success: function (data) {
                    if (data.success) {
                        self.sendAnalytics();
                        self.preparingMultimediaExport(false);
                        self.downloadInProgress(true);
                        self.progressModel.downloadCookieName(self.savedMultimediaDownloadCookieName);
                        self.progressModel.startMultimediaDownload(data.download_id);
                    } else {
                        self.handleError(data);
                    }
                },
                error: self.handleError,
            });
        };

        self.handleError = function (data) {
            if (data && data.error) {
                // The server returned an error message.
                self.prepareExportError(data.error);
            } else {
                self.prepareExportError(gettext("Sorry, there was a problem reaching the server. Please try again."));
            }
            self.preparingExport(false);
            self.preparingMultimediaExport(false);
        };

        return self;
    };

    var downloadProgressModel = function (options) {
        assertProperties.assert(options, ['exportType', 'formOrCase', 'emailUrl', 'pollUrl']);

        var self = {};

        self.exportType = options.exportType;
        self.formOrCase = options.formOrCase;
        self.downloadId = ko.observable();
        self.progress = ko.observable();
        self.downloadCookieName = ko.observable();
        self.storeDownloadCookie = function () {
            if (self.downloadCookieName() && self.downloadId()) {
                $.cookie(self.downloadCookieName(), self.downloadId(), { path: '/', secure: initialPageData.get('secure_cookies') });
            }
        };
        self.clearDownloadCookie = function () {
            if (self.downloadCookieName()) {
                $.removeCookie(self.downloadCookieName(), { path: '/' });
            }
        };

        // URLs for user actions
        self.pollUrl = options.pollUrl;
        self.emailUrl = options.emailUrl;

        // URLs related to the completed download
        self.dropboxUrl = ko.observable();
        self.downloadUrl = ko.observable();

        // UI flags
        self.showDownloadStatus = ko.observable();
        self.isDownloaded = ko.observable();
        self.isDownloadReady = ko.observable();
        self.isMultimediaDownload = ko.observable();
        self.sendEmailFlag = ko.observable();

        // Error handling
        self.progressError = ko.observable();
        self.celeryError = ko.observable('');
        self.downloadError = ko.observable('');
        self.showError = ko.computed(function () {
            return self.celeryError() || self.downloadError();
        });

        self.resetDownload = function () {
            self.downloadId(null);
            self._numErrors = 0;
            self._numCeleryRetries = 0;
            self._lastProgress = 0;
            self.showDownloadStatus(false);
            self.isDownloadReady(false);
            self.isDownloaded(false);
            self.celeryError('');
            self.downloadError('');
            self.isMultimediaDownload(false);
            self.progress(0);
            self.progressError('');
            self.sendEmailFlag(false);
            self.dropboxUrl('');
            self.downloadUrl('');
        };
        self.resetDownload();

        self.startDownload = function (downloadId) {
            self.showDownloadStatus(true);
            self.downloadId(downloadId);
            self.storeDownloadCookie();
            self.interval = setInterval(self._checkDownloadProgress, 2000);
        };

        self.startMultimediaDownload = function (downloadId) {
            self.isMultimediaDownload(true);
            self.startDownload(downloadId);
        };

        self.clickDownload = function () {
            self.isDownloaded(true);
            self.sendAnalytics();
            self.clearDownloadCookie();
            return true;    // allow default click action
        };

        self.sendAnalytics = function () {
            googleAnalytics.track.event("Download Export", exportUtils.capitalize(self.exportType), "Saved");
            kissmetricsAnalytics.track.event("Clicked Download button");
        };

        self._checkDownloadProgress = function () {
            $.ajax({
                method: 'GET',
                url: self.pollUrl,
                data: {
                    form_or_case: self.formOrCase,
                    download_id: self.downloadId,
                },
                success: function (data) {
                    if (data.is_poll_successful) {
                        self._updateProgressBar(data);
                        self.downloadId(data.download_id);
                        if (data.has_file && data.is_ready) {
                            clearInterval(self.interval);
                            return;
                        }
                        if (data.progress && data.progress.error) {
                            clearInterval(self.interval);
                            self.progressError(data.progress.error_message);
                            self.clearDownloadCookie();
                            return;
                        }
                        if (data.progress.current > self._lastProgress) {
                            self._lastProgress = data.progress.current;
                            // processing is still going, keep moving.
                            // this avoids failing hard prematurely at celery errors if
                            // the polling is still reporting forward progress.
                            self._numCeleryRetries = 0;
                            return;
                        }
                    }
                    if (data.error) {
                        self._dealWithErrors(data);
                    }
                    if (_.isNull(data.is_alive)) {
                        self._dealWithCeleryErrors();
                    }
                },
                error: self._dealWithErrors,
            });
        };

        self._dealWithCeleryErrors = function () {
            // Sometimes the task handler for celery is a little slow to get
            // started, so we have to try a few times.
            if (self._numCeleryRetries > 10) {
                clearInterval(self.interval);
                self.clearDownloadCookie();
                self.celeryError(gettext("Server maintenance in progress. Please try again later."));
            }
            self._numCeleryRetries ++;
        };

        self._dealWithErrors = function (data) {
            if (self._numErrors > 3) {
                if (data && data.error) {
                    self.downloadError(data.error);
                } else {
                    self.downloadError(gettext("There was an error downloading your export."));
                }
                clearInterval(self.interval);
                self.clearDownloadCookie();
            }
            self._numErrors ++;
        };

        self._updateProgressBar = function (data) {
            var progressPercent = 0;
            if (data.is_ready && data.has_file) {
                progressPercent = 100;
                self.isDownloadReady(true);
                self.dropboxUrl(data.dropbox_url);
                self.downloadUrl(data.download_url);
            } else if (_.isNumber(data.progress.percent)) {
                progressPercent = data.progress.percent;
            }
            self.progress(progressPercent);
        };

        self.sendEmailUponCompletion = function () {
            self.sendEmailFlag(true);
            $.ajax({
                method: 'POST',
                dataType: 'json',
                url: self.emailUrl,
                data: { download_id: self.downloadId },
            });
        };

        return self;
    };

    $(function () {
        reportFilters.init();

        var exportList = initialPageData.get('export_list'),
            exportType = exportList[0].export_type;

        var progressModel = downloadProgressModel({
            exportType: exportType,
            emailUrl: initialPageData.reverse('add_export_email_request'),
            formOrCase: initialPageData.get('form_or_case'),
            pollUrl: initialPageData.reverse('poll_custom_export_download'),
        });

        $("#download-export-form").koApplyBindings(downloadFormModel({
            defaultDateRange: initialPageData.get('default_date_range'),
            exportList: exportList,
            exportType: exportType,
            formOrCase: initialPageData.get('form_or_case'),
            maxColumnSize: initialPageData.get('max_column_size') || 2000,
            multimediaUrl: initialPageData.get('check_for_multimedia') ? initialPageData.reverse('has_multimedia') : '',
            progressModel: progressModel,
            prepareUrl: initialPageData.reverse('prepare_custom_export'),
            prepareMultimediaUrl: initialPageData.reverse('prepare_form_multimedia'),
            smsExport: initialPageData.get('sms_export'),
            userTypes: initialPageData.get('user_types'),
        }));

        $("#download-progress").koApplyBindings(progressModel);

        $(".hqwebapp-datespan").each(function () {
            var $el = $(this).find("input");
            $el.createDateRangePicker(
                $el.data("labels"),
                $el.data("separator"),
                $el.data('startDate'),
                $el.data('endDate')
            );
        });
    });
});
