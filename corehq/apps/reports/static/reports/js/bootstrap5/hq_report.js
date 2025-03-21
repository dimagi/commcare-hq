hqDefine("reports/js/bootstrap5/hq_report", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/bootstrap5/alert_user',
    'analytix/js/kissmetrix',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap5/widgets', //multi-emails
], function (
    $,
    ko,
    _,
    alertUser,
    kissmetrics,
    initialPageData,
    widgets,  // eslint-disable-line no-unused-vars
) {
    var hqReport = function (options) {
        var self = {};
        self.domain = options.domain;
        self.datespan = options.datespan;
        self.filterSet = options.filterSet || false;
        self.needsFilters = options.needsFilters || false;
        self.filterAccordion = options.filterAccordion || "#reportFilters" + initialPageData.get('html_id_suffix');
        self.filterSubmitSelector = options.filterSubmitSelector || '#paramSelectorForm' + initialPageData.get('html_id_suffix') + ' button[type="submit"]';
        self.filterSubmitButton = $(self.filterSubmitSelector);
        self.toggleFiltersButton = options.toggleFiltersButton || "#toggle-report-filters" + initialPageData.get('html_id_suffix');
        self.exportReportButton = options.exportReportButton || "#export-report-excel" + initialPageData.get('html_id_suffix');
        self.emailReportButton = options.emailReportButton || "#email-report" + initialPageData.get('html_id_suffix');
        self.printReportButton = options.printReportButton || "#print-report" + initialPageData.get('html_id_suffix');
        self.emailReportModal = options.emailReportModal || "#email-report-modal" + initialPageData.get('html_id_suffix');
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
                if (self.slug) {
                    if (self.isExportable) {
                        $(self.exportReportButton).click(function (e) {
                            e.preventDefault();
                            if (self.isExportAll) {
                                $.ajax({
                                    url: self.getReportBaseUrl("export"),
                                    data: self.getReportParams(undefined),
                                    type: "POST",
                                    success: function () {
                                        alertUser.alert_user(gettext("Your requested Excel report will be sent " +
                                            "to the email address defined in your account settings."), "success");
                                    },
                                });
                            } else {
                                window.location.href = self.getReportRenderUrl("export");
                            }
                        });
                    }

                    if (self.isEmailable) {
                        self.emailReportViewModel = new EmailReportViewModel(self);
                        $(self.emailReportModal).koApplyBindings(self.emailReportViewModel);
                    }

                    $(self.printReportButton).click(function (e) {
                        e.preventDefault();
                        window.open(self.getReportRenderUrl("print"));
                    });

                    trackReportPageEnter();
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
            $(self.filterAccordion).addClass('show');
            $(self.toggleFiltersButton).changeButtonState('close');

            var hiddenFilterButtonStatus = function (data) {
                if (!(data.target && $(data.target).hasClass('modal'))) {
                    $(self.toggleFiltersButton).changeButtonState('open');
                }
            };

            $(self.filterAccordion).on('hidden.bs.collapse', hiddenFilterButtonStatus);

            var showFilterButtonStatus = function () {
                $(self.toggleFiltersButton).changeButtonState('close');
            };

            $(self.filterAccordion).on('show.bs.collapse', showFilterButtonStatus);

        };

        $(self.filterAccordion).on('hqreport.filter.datespan.startdate', function (event, value) {
            self.datespan.startdate = value;
        });

        $(self.filterAccordion).on('hqreport.filter.datespan.enddate', function (event, value) {
            self.datespan.enddate = value;
        });

        self.resetFilterState = function () {
            $('#paramSelectorForm' + initialPageData.get('html_id_suffix') + ' fieldset button, #paramSelectorForm' + initialPageData.get('html_id_suffix') + ' fieldset span[data-dropdown="dropdown"]').click(function () {
                $(self.filterSubmitSelector)
                    .changeButtonState('reset')
                    .addClass('btn-primary')
                    .removeClass('disabled')
                    .prop('disabled', false);
            });
            $('#paramSelectorForm' + initialPageData.get('html_id_suffix') + ' fieldset').on('change apply', function (e) {
                // Ensure correct submit button is found in context of which form the button belongs to.
                // This is necessary for pages that contain multiple filter panels, since we are using CSS IDs.
                const submitButton = $(e.target).closest('#reportFilters' + initialPageData.get('html_id_suffix')).find(self.filterSubmitSelector);
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
                    url: self.getReportBaseUrl('get_or_create_hash'),
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
            var baseUrl = self.getReportBaseUrl(renderType);
            var paramString = self.getReportParams(additionalParams);
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

        /**
         * Send a Kissmetrics event, depending on report page slug
         */
        function trackReportPageEnter() {
            switch (self.slug) {
                case 'submit_history':
                    kissmetrics.track.event('Visited Submit History Page');
                    break;
                case 'case_list':
                    kissmetrics.track.event('Visited Case List Page');
                    break;
                default:
                    break;
            }
        }

        return self;
    };
    return {
        hqReport: hqReport,
    };
});
