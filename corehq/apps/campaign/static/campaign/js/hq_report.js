hqDefine("campaign/js/hq_report", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/bootstrap5/alert_user',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap5/widgets', //multi-emails
], function (
    $,
    ko,
    _,
    alertUser,
    initialPageData,
    widgets,  // eslint-disable-line no-unused-vars
) {
    var hqReport = function (options) {
        var self = {};
        self.widgetFilters = options.widgetFilters;  // Filters element
        self.datespan = options.datespan;
        self.filterSet = options.filterSet || false;
        self.needsFilters = options.needsFilters || false;
        self.reportId = options.reportConfigurationId || options.subReportSlug;
        self.filterAccordion = options.filterAccordion || "#reportFilters-" + self.reportId;
        self.filterSubmitSelector = options.filterSubmitSelector || '#paramSelectorForm-' + self.reportId + ' button[type="submit"]';
        self.filterSubmitButton = self.widgetFilters.find(self.filterSubmitSelector);
        self.toggleFiltersButton = options.toggleFiltersButton || "#toggle-report-filters-" + self.reportId;
        self.exportReportButton = options.exportReportButton || "#export-report-excel-" + self.reportId;
        self.emailReportButton = options.emailReportButton || "#email-report-" + self.reportId;
        self.printReportButton = options.printReportButton || "#print-report-" + self.reportId;
        self.emailReportModal = options.emailReportModal || "#email-report-modal-" + self.reportId;
        self.isExportable = options.isExportable || false;
        self.isExportAll = options.isExportAll || false;
        self.isEmailable = options.isEmailable || false;
        self.emailDefaultSubject = options.emailDefaultSubject || "";
        self.emailSuccessMessage = options.emailSuccessMessage;
        self.emailErrorMessage = options.emailErrorMessage;
        self.urlRoot = options.urlRoot;
        self.slug = options.slug;
        self.subReportSlug = options.subReportSlug;
        self.type = options.type;
        self.getReportRenderUrl = options.getReportRenderUrl || getReportRenderUrl;
        self.getReportBaseUrl = options.getReportBaseUrl || getReportBaseUrl;
        self.getReportParams = options.getReportParams || getReportParams;

        self.cookieDatespanStart = 'hqreport.filterSetting.datespan.startdate';
        self.cookieDatespanEnd = 'hqreport.filterSetting.datespan.enddate';

        self.initialLoad = true;

        self.init = function () {
            $(function () {
                checkFilterAccordionToggleState();

                self.resetFilterState();

                if (self.needsFilters) {
                    self.filterSubmitButton
                        .changeButtonState('reset')
                        .addClass('btn-primary')
                        .removeClass('disabled')
                        .prop('disabled', false);
                }
            });
        };

        self.handleTabularReportCookies = function (reportDatatable) {
            var defaultRowsCookieName = 'hqreport.tabularSetting.defaultRows',
                savedPath = window.location.pathname;

            if (!reportDatatable.forcePageSize) {
                // set the current pagination page size to be equal to page size
                // used by the user last time for any report on HQ
                var defaultRowsCookie = '' + $.cookie(defaultRowsCookieName);
                reportDatatable.defaultRows = parseInt(defaultRowsCookie) || reportDatatable.defaultRows;
            }

            $(reportDatatable.dataTableElem).on('hqreport.tabular.lengthChange', function (event, value) {
                $.cookie(defaultRowsCookieName, value, {
                    path: savedPath,
                    expires: 2,
                    secure: initialPageData.get('secure_cookies'),
                });
            });
        };

        self.saveDatespanToCookie = function () {
            var validDate = /^\d{4}-\d{2}-\d{2}$/;
            if (self.datespan && validDate.test(self.datespan.startdate) && validDate.test(self.datespan.enddate)) {
                $.cookie(self.cookieDatespanStart, self.datespan.startdate, {
                    path: self.urlRoot,
                    expires: 1,
                    secure: initialPageData.get('secure_cookies'),
                });
                $.cookie(self.cookieDatespanEnd, self.datespan.enddate, {
                    path: self.urlRoot,
                    expires: 1,
                    secure: initialPageData.get('secure_cookies'),
                });
            }
        };

        self.loadDatespanFromCookie = function () {
            if (self.datespan) {
                var cookieStartDate = $.cookie(self.cookieDatespanStart),
                    cookieEndDate = $.cookie(self.cookieDatespanEnd),
                    loadSuccess = false;

                if (cookieEndDate && cookieStartDate) {
                    loadSuccess = true;
                    self.datespan.startdate = cookieStartDate;
                    self.datespan.enddate = cookieEndDate;
                }
            }
            return loadSuccess;
        };

        var checkFilterAccordionToggleState = function () {
            self.widgetFilters.find(self.filterAccordion).addClass('show');
            self.widgetFilters.find(self.toggleFiltersButton).changeButtonState('close');

            var hiddenFilterButtonStatus = function (data) {
                if (!(data.target && $(data.target).hasClass('modal'))) {
                    self.widgetFilters.find(self.toggleFiltersButton).changeButtonState('open');
                }
            };

            self.widgetFilters.find(self.filterAccordion).on('hidden.bs.collapse', hiddenFilterButtonStatus);

            var showFilterButtonStatus = function () {
                self.widgetFilters.find(self.toggleFiltersButton).changeButtonState('close');
            };

            self.widgetFilters.find(self.filterAccordion).on('show.bs.collapse', showFilterButtonStatus);

        };

        self.widgetFilters.find(self.filterAccordion).on('hqreport.filter.datespan.startdate', function (event, value) {
            self.datespan.startdate = value;
        });

        self.widgetFilters.find(self.filterAccordion).on('hqreport.filter.datespan.enddate', function (event, value) {
            self.datespan.enddate = value;
        });

        self.resetFilterState = function () {
            // Find all buttons and dropdowns within the form and attach click handlers
            self.widgetFilters.find('#paramSelectorForm-' + self.reportId + ' fieldset button, #paramSelectorForm-' + self.reportId + ' fieldset span[data-dropdown="dropdown"]').click(function () {
                self.widgetFilters.find(self.filterSubmitSelector)
                    .changeButtonState('reset')
                    .addClass('btn-primary')
                    .removeClass('disabled')
                    .prop('disabled', false);
            });
            
            // Attach change handlers to all form elements
            self.widgetFilters.find('#paramSelectorForm-' + self.reportId + ' fieldset').on('change apply', function (e) {
                // Ensure correct submit button is found in context of which form the button belongs to.
                // This is necessary for pages that contain multiple filter panels, since we are using CSS IDs.
                const submitButton = $(e.target).closest('#reportFilters-' + self.reportId).find(self.filterSubmitSelector);
                $(submitButton)
                    .changeButtonState('reset')
                    .addClass('btn-primary')
                    .removeClass('disabled')
                    .prop('disabled', false);
            });
        };

        function getReportParams(additionalParams) {
            var params = window.location.search.substr(1);
            if (params.includes('query_id=')) {
                // getting the proper params for reports with obfuscated urls (Case List Explorer)
                $.ajax({
                    url: self.urlRoot + 'get_or_create_hash/',
                    type: 'POST',
                    dataType: 'json',
                    async: false,
                    data: {
                        'query_id': params.replace('query_id=', ''),
                        'params': '',
                    },
                    success: function (data) {
                        params = data.query_string;
                    },
                });
            }
            if (params.length <= 1) {
                if (self.loadDatespanFromCookie()) {
                    params = "startdate=" + self.datespan.startdate + "&enddate=" + self.datespan.enddate;
                }
            }
            params += (additionalParams ? "&" + additionalParams : "");
            return params;
        }

        function getReportBaseUrl(renderType) {
            return window.location.pathname.replace(self.urlRoot, self.urlRoot + renderType + "/");
        }

        function getReportRenderUrl(renderType, additionalParams) {
            var baseUrl = getReportBaseUrl(renderType);
            var paramString = getReportParams(additionalParams);
            return baseUrl + "?" + paramString;
        }

        function EmailReportViewModel(hqReport) {
            var self = this;

            self.send_to_owner = ko.observable(true);
            self.subject = ko.observable(hqReport.emailDefaultSubject);
            self.recipient_emails = ko.observableArray();
            self.notes = ko.observable();
            self.getReportRenderUrl = hqReport.getReportRenderUrl;
            self.params = hqReport.getReportParams;

            self.unwrap = function () {
                var data = ko.mapping.toJS(self, {
                    ignore: ['sendEmail', 'unwrap', 'resetModal', 'getReportRenderUrl'],
                });

                for (var i in data) {
                    if (data[i] === null || data[i] === undefined) {
                        delete data[i];
                    }
                }
                return data;
            };

            self.sendEmail = function () {
                var $sendButton = $(hqReport.emailReportModal).find('.send-button');
                $sendButton.changeButtonState('loading');

                $.post(getReportBaseUrl("email_onceoff"), $.param(self.unwrap()))
                    .done(function () {
                        $(hqReport.emailReportModal).modal('hide');  /* todo B5: plugin:modal */
                        self.resetModal();
                        alertUser.alert_user(hqReport.emailSuccessMessage, "success");
                    })
                    .fail(function (response) {
                        $(hqReport.emailReportModal).modal('hide');  /* todo B5: plugin:modal */
                        self.resetModal();
                        const errors = JSON.parse(response.responseText);
                        let messages = [hqReport.emailErrorMessage].concat(errors);
                        const message = messages.join('<br/>');
                        alertUser.alert_user(message, "error");
                    });
            };

            self.resetModal = function () {
                $(hqReport.emailReportModal).find('.send-button').changeButtonState('reset');  /* todo B5: plugin:button */
            };
        }
        return self;
    };
    return {
        hqReport: hqReport,
    };
});
