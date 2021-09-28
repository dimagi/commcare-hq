hqDefine("reports/js/hq_report", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/alert_user',
    'analytix/js/kissmetrix',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    alertUser,
    kissmetrics,
    initialPageData
) {
    var hqReport = function (options) {
        'use strict';
        var self = {};
        self.domain = options.domain;
        self.datespan = options.datespan;
        self.filterSet = options.filterSet || false;
        self.needsFilters = options.needsFilters || false;
        self.filterAccordion = options.filterAccordion || "#reportFilters";
        self.filterSubmitSelector = options.filterSubmitSelector || '#paramSelectorForm button[type="submit"]';
        self.filterSubmitButton = $(self.filterSubmitSelector);
        self.toggleFiltersButton = options.toggleFiltersButton || "#toggle-report-filters";
        self.exportReportButton = options.exportReportButton || "#export-report-excel";
        self.emailReportButton = options.emailReportButton || "#email-report";
        self.printReportButton = options.printReportButton || "#print-report";
        self.emailReportModal = options.emailReportModal || "#email-report-modal";
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
                        .button('reset')
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
                                    url: getReportBaseUrl("export"),
                                    data: getReportParams(undefined),
                                    type: "POST",
                                    success: function () {
                                        alertUser.alert_user(gettext("Your requested Excel report will be sent to the email " +
                                            "address defined in your account settings."), "success");
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
            var defaultRowsCookie = '' + $.cookie(defaultRowsCookieName);
            reportDatatable.defaultRows = parseInt(defaultRowsCookie) || reportDatatable.defaultRows;

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
                var cookie_startdate = $.cookie(self.cookieDatespanStart),
                    cookie_enddate = $.cookie(self.cookieDatespanEnd),
                    load_success = false;

                if (cookie_enddate && cookie_startdate) {
                    load_success = true;
                    self.datespan.startdate = cookie_startdate;
                    self.datespan.enddate = cookie_enddate;
                }
            }
            return load_success;
        };

        var checkFilterAccordionToggleState = function () {
            $(self.filterAccordion).addClass('in');
            $(self.toggleFiltersButton).button('close');

            var hiddenFilterButtonStatus = function (data) {
                if (!(data.target && $(data.target).hasClass('modal'))) {
                    $(self.toggleFiltersButton).button('open');
                }
            };

            $(self.filterAccordion).on('hidden.bs.collapse', hiddenFilterButtonStatus);

            var showFilterButtonStatus = function () {
                $(self.toggleFiltersButton).button('close');
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
            $('#paramSelectorForm fieldset button, #paramSelectorForm fieldset span[data-dropdown="dropdown"]').click(function () {
                $(self.filterSubmitSelector)
                    .button('reset')
                    .addClass('btn-primary')
                    .removeClass('disabled')
                    .prop('disabled', false);
            });
            $('#paramSelectorForm fieldset').on('change apply', function () {
                $(self.filterSubmitSelector)
                    .button('reset')
                    .addClass('btn-primary')
                    .removeClass('disabled')
                    .prop('disabled', false);
            });
        };

        function getReportParams(additionalParams) {
            var params = window.location.search.substr(1);
            if (params.length <= 1) {
                if (self.loadDatespanFromCookie()) {
                    params = "startdate=" + self.datespan.startdate +
                        "&enddate=" + self.datespan.enddate;
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
            self.recipient_emails = ko.observable();
            self.notes = ko.observable();
            self.getReportRenderUrl = hqReport.getReportRenderUrl;

            self.unwrap = function () {
                var data = ko.mapping.toJS(self, {
                    ignore: ['sendEmail', 'unwrap', 'resetModal'],
                });

                for (var i in data) {
                    if (data[i] === null || data[i] === undefined) delete data[i];
                }
                return data;
            };

            self.sendEmail = function () {
                var $sendButton = $(hqReport.emailReportModal).find('.send-button');
                $sendButton.button('loading');

                $.get(self.getReportRenderUrl("email_onceoff", $.param(self.unwrap())))
                    .done(function () {
                        $(hqReport.emailReportModal).modal('hide');
                        self.resetModal();
                        alertUser.alert_user(hqReport.emailSuccessMessage, "success");
                    })
                    .fail(function () {
                        $(hqReport.emailReportModal).modal('hide');
                        self.resetModal();
                        alertUser.alert_user(hqReport.emailErrorMessage, "error");
                    });
            };

            self.resetModal = function () {
                $(hqReport.emailReportModal).find('.send-button').button('reset');
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
