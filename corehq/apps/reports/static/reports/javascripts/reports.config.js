var HQReport = function (options) {
    'use strict';
    var self = this;
    self.domain = options.domain;
    self.datespan = options.datespan;
    self.filterSet = options.filterSet || false;
    self.needsFilters = options.needsFilters || false;
    self.filterAccordion = options.filterAccordion || "#reportFilters";
    self.filterSubmitButton = options.filterSubmitButton || $('#paramSelectorForm button[type="submit"]');
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

    self.toggleFiltersCookie = self.domain+'.hqreport.toggleFilterState';
    self.datespanCookie = self.domain+".hqreport.filterSetting.test.datespan";

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
                    .removeProp('disabled');
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
                                success: function() {
                                    alert_user("Your requested excel report will be sent to the email address " +
                                               "defined in your account settings.", "success");
                                }
                            })
                        } else {
                            window.location.href = getReportRenderUrl("export");
                        }
                    });
                }

                if (self.isEmailable) {
                    self.emailReportViewModel = new EmailReportViewModel(self);
                    $(self.emailReportModal).koApplyBindings(self.emailReportViewModel);
                }

                $(self.printReportButton).click(function (e) {
                    e.preventDefault();
                    window.open(getReportRenderUrl("print"));
                });
            }
        });
    };

    self.handleTabularReportCookies = function (reportDatatable) {
        var defaultRowsCookieName = self.domain+'.hqreport.tabularSetting.defaultRows',
            savedPath = window.location.pathname;
        var defaultRowsCookie = ''+$.cookie(defaultRowsCookieName);
        reportDatatable.defaultRows = parseInt(defaultRowsCookie) || reportDatatable.defaultRows;

        $(reportDatatable.dataTableElem).on('hqreport.tabular.lengthChange', function (event, value) {
            $.cookie(defaultRowsCookieName, value,
                {path: savedPath, expires: 2});
        });
    };

    self.saveDatespanToCookie = function () {
        var validDate = /^\d{4}-\d{2}-\d{2}$/;
        if (self.datespan && validDate.test(self.datespan.startdate) && validDate.test(self.datespan.enddate)) {
            $.cookie(self.datespanCookie+'.startdate', self.datespan.startdate,
                {path: self.urlRoot, expires: 1});
            $.cookie(self.datespanCookie+'.enddate', self.datespan.enddate,
                {path: self.urlRoot, expires: 1});
        }
    };

    self.loadDatespanFromCookie = function () {
        if (self.datespan) {
            var cookie_startdate = $.cookie(self.datespanCookie+'.startdate'),
                cookie_enddate = $.cookie(self.datespanCookie+'.enddate'),
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
        var _setShowFilterCookie = function (show) {
            var showStr = show ? 'in' : '';
            $.cookie(self.toggleFiltersCookie, showStr, {path: self.urlRoot, expires: 1});
        };
        
        if (!$.cookie(self.toggleFiltersCookie) && $.cookie(self.toggleFiltersCookie) !== '') {
            // default to showing filters
            // (When filters should be hidden, $.cookie(self.toggleFiltersCookie) === '')
            _setShowFilterCookie(true);
        }
        $(self.filterAccordion).addClass($.cookie(self.toggleFiltersCookie));

        if ($.cookie(self.toggleFiltersCookie) == 'in') {
            $(self.toggleFiltersButton).button('close');
        } else {
            $(self.toggleFiltersButton).button('open');
        }

        var hiddenFilterButtonStatus = function (data) {
            if (!(data.target && $(data.target).hasClass('modal'))) {
                _setShowFilterCookie(false);
                $(self.toggleFiltersButton).button('open');
            }
        };

        $(self.filterAccordion).on('hidden', hiddenFilterButtonStatus);  // B2 event
        $(self.filterAccordion).on('hidden.bs.collapse', hiddenFilterButtonStatus);  // B3 event

        var showFilterButtonStatus = function () {
            _setShowFilterCookie(true);
            $(self.toggleFiltersButton).button('close');
        };

        $(self.filterAccordion).on('show', showFilterButtonStatus);  // B2 event
        $(self.filterAccordion).on('show.bs.collapse', showFilterButtonStatus);  // B3 event

    };

    $(self.filterAccordion).on('hqreport.filter.datespan.startdate', function(event, value) {
        self.datespan.startdate = value;
    });

    $(self.filterAccordion).on('hqreport.filter.datespan.enddate', function(event, value) {
        self.datespan.enddate = value;
    });

    self.resetFilterState = function () {
        $('#paramSelectorForm fieldset button, #paramSelectorForm fieldset span[data-dropdown="dropdown"]').click(function() {
            $('#paramSelectorForm button[type="submit"]')
                .button('reset')
                .addClass('btn-primary')
                .removeClass('disabled')
                .removeProp('disabled');
        });
        $('#paramSelectorForm fieldset').on('change apply', function () {
            $('#paramSelectorForm button[type="submit"]')
                .button('reset')
                .addClass('btn-primary')
                .removeClass('disabled')
                .removeProp('disabled');
        });
    };

    function getReportParams(additionalParams) {
        var params = window.location.search.substr(1);
        if (params.length <= 1) {
            if (self.loadDatespanFromCookie()) {
                params = "startdate="+self.datespan.startdate+
                    "&enddate="+self.datespan.enddate;
            }
        }
        params += (additionalParams ? "&" + additionalParams : "");
        return params;

    }

    function getReportBaseUrl(renderType) {
        return window.location.pathname.replace(self.urlRoot, self.urlRoot+renderType+"/");
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

        self.unwrap = function () {
            var data = ko.mapping.toJS(self, {
                ignore: ['sendEmail', 'unwrap', 'resetModal']
            });

            for (var i in data) {
                if (data[i] === null || data[i] === undefined) delete data[i];
            }
            return data;
        };

        self.sendEmail = function () {
             var $sendButton = $(hqReport.emailReportModal).find('.send-button');
             $sendButton.button('loading');

            $.get(getReportRenderUrl("email_onceoff", $.param(self.unwrap())))
                .done(function() {
                    $(hqReport.emailReportModal).modal('hide');
                    self.resetModal();
                    $.showMessage(hqReport.emailSuccessMessage, "success");
                })
                .fail(function() {
                    $(hqReport.emailReportModal).modal('hide');
                    self.resetModal();
                    $.showMessage(hqReport.emailErrorMessage, "error");
                });
        };

        self.resetModal = function () {
            $(hqReport.emailReportModal).find('.send-button').button('reset');
        };
    }
};
