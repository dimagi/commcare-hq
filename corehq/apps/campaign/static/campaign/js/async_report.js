hqDefine("campaign/js/async_report", [
    'jquery',
    'underscore',
    'bootstrap5',
    'hqwebapp/js/bootstrap5/alert_user',
    'reports/js/charts/main',
    'reports/js/filters/bootstrap5/main',
    'reports/js/util',
], function (
    $,
    _,
    bootstrap,
    alertUser,
    chartsMain,
    filtersMain,
    reportsUtil,
) {
    return function (o) {
        var self = {};
        self.widgetFilters = o.widgetFilters;
        self.reportContent = o.reportContent;
        self.filterForm = o.filterForm;
        self.loadingIssueModalElem = self.reportContent.find('#loadingReportIssueModal');
        self.loadingIssueModal = new bootstrap.Modal(self.loadingIssueModalElem.get(0));
        self.issueAttempts = 0;
        self.urlRoot = o.urlRoot;
        self.hqLoading = null;
        self.standardReport = o.standardReport;
        self.filterRequest = null;
        self.reportRequest = null;
        self.queryIdRequest = null;
        self.loaderClass = '.report-loading';
        self.maxInputLimit = 4500;

        self.humanReadableErrors = {
            400: gettext("Please check your Internet connection!"),
            404: gettext("Report Not Found."),
            408: gettext("Request timed out when rendering this report. This might be an issue with our servers" +
                " or with your Internet connection. We encourage you to report an issue to CommCare HQ Support so we" +
                " can look into any possible issues."),
            500: gettext("Problem Rendering Report. Our error monitoring tools have noticed this and we are working quickly to" +
                " resolve this issue as soon as possible. We encourage you to contact CommCare HQ Support" +
                " if this issue persists for more than a few minutes. We appreciate any additional information" +
                " you can give us about this problem so we can fix it immediately."),
            502: gettext("Bad Gateway. Please contact CommCare HQ Support."),
            503: gettext("CommCare HQ is experiencing server difficulties. We're working quickly to resolve it." +
                " Thank you for your patience. We are extremely sorry."),
            504: gettext("Gateway Timeout. Please contact CommCare HQ Support."),
            'maxInputError': gettext("Your search term was too long. Please provide a shorter search filter"),
        };

        var loadFilters = function (data) {
            self.filterRequest = null;
            try {
                self.widgetFilters.find('#hq-report-filters').html(data.filters);
                filtersMain.init();
            } catch (e) {
                console.log(e);
            }
            self.widgetFilters.find('#reportFiltersAccordion').removeClass('d-none');
            self.standardReport.resetFilterState();
        };

        self.init = function () {
            self.reportContent.attr('style', 'position: relative;');
            var initParams = window.location.search.substr(1);
            var pathName = window.location.pathname;
            if (initParams && self.isCaseListRelated(pathName)) {
                self.getQueryId(initParams, true, self.standardReport.filterSet, pathName);
            } else {
                self.updateReport(true, initParams, self.standardReport.filterSet);
            }

            // only update the report if there are actually filters set
            if (!self.standardReport.needsFilters) {
                self.standardReport.filterSubmitButton.addClass('disabled');
            }
            self.filterForm.submit(function () {
                var params = reportsUtil.urlSerialize(this);
                if (self.isCaseListRelated(pathName)) {
                    var url = window.location.href.replace(self.standardReport.urlRoot,
                        self.standardReport.urlRoot + 'async/') + "?" + "&" + params;
                    if (url.length > self.maxInputLimit) {
                        alertUser.alert_user(self.humanReadableErrors['maxInputError'], "danger");
                    } else {
                        self.getQueryId(params, false, true, pathName);
                    }
                } else {
                    self.updateFilters(params);
                    self.updateReport(false, params, true);
                    history.pushState(null,window.location.title, window.location.pathname + '?' + params);
                }
                return false;
            });
        };

        self.isCaseListRelated = function (pathName) {
            return pathName.includes('case_list');
        };

        self.getQueryId = function (params, initialLoad, setFilters, pathName) {
            // This only applies to Case List and Case List Explorer filter queries
            var queryId;
            if (params.includes('query_id=')) {
                queryId = params.replace('query_id=', '');
                params = '';
            } else {
                queryId = '';
            }
            self.queryIdRequest = $.ajax({
                // url: pathName.replace(self.standardReport.urlRoot, self.standardReport.urlRoot + 'get_or_create_hash/'),
                url: self.urlRoot + 'get_or_create_hash/',
                type: 'POST',
                dataType: 'json',
                data: {
                    'query_id': queryId,
                    'params': params,
                },
                success: function (data) {
                    self.queryIdRequest = null;
                    if (data.not_found) {
                        // no corresponding filter config found - redirect to the landing page
                        window.location.href = window.location.href.split('?')[0];
                    } else {
                        if (!initialLoad) { self.updateFilters(data.query_string); }
                        self.updateReport(initialLoad, data.query_string, setFilters);
                        history.pushState(null, window.location.title, pathName + '?query_id=' + data.query_id);
                    }
                },
            });
        };

        self.updateFilters = function (params) {
            self.standardReport.saveDatespanToCookie();
            self.filterRequest = $.ajax({
                // url: window.location.pathname.replace(self.standardReport.urlRoot,
                //     self.standardReport.urlRoot + 'filters/') + "?" + params,
                url: self.urlRoot + 'filters/' + "?" + params,
                dataType: 'json',
                success: loadFilters,
            });
        };

        self.updateReport = function (initialLoad, params, setFilters) {
            var processFilters = "";
            if (initialLoad) {
                processFilters = "hq_filters=true&";
                if (self.standardReport.loadDatespanFromCookie()) {
                    processFilters = processFilters +
                        "&startdate=" + self.standardReport.datespan.startdate +
                        "&enddate=" + self.standardReport.datespan.enddate;
                }
            }
            if (setFilters !== undefined) {
                processFilters = processFilters + "&filterSet=" + setFilters;
            }
            if (setFilters) {
                // TODO: widgetFilters or reportContent?
                self.widgetFilters.find(self.standardReport.exportReportButton).removeClass('d-none');
                self.widgetFilters.find(self.standardReport.emailReportButton).removeClass('d-none');
                self.widgetFilters.find(self.standardReport.printReportButton).removeClass('d-none');
            }

            self.reportRequest = $.ajax({
                // url: (window.location.pathname.replace(self.standardReport.urlRoot,
                //     self.standardReport.urlRoot + 'async/')) + "?" + processFilters + "&" + params,
                url: self.urlRoot + 'async/' + "?" + processFilters + "&" + params,
                dataType: 'json',
                success: function (data) {
                    self.reportRequest = null;
                    if (data.filters) {
                        loadFilters(data);
                    }
                    self.issueAttempts = 0;
                    if (self.loadingIssueModalElem.hasClass('show')) {
                        self.loadingIssueModal.hide();
                    }
                    self.hqLoading = self.reportContent.find(self.loaderClass);
                    self.reportContent.html(data.report);
                    chartsMain.init();
                    // clear lingering popovers
                    _.each(self.reportContent.find('body > .popover'), function (popover) {
                        self.reportContent.find(popover).remove();
                    });
                    self.reportContent.append(self.hqLoading);
                    self.hqLoading.removeClass('d-none');

                    // Assorted UI cleanup/initialization
                    self.reportContent.find('.hq-report-time-notice').removeClass('d-none');

                    self.reportContent.find('.loading-backdrop').fadeOut();
                    self.hqLoading.fadeOut();

                    if (!initialLoad || !self.standardReport.needsFilters) {
                        self.standardReport.filterSubmitButton
                            .changeButtonState('reset');
                        setTimeout(function () {
                            // Bootstrap clears all btn styles except btn on reset
                            // This gets around it by waiting 10ms.
                            self.standardReport.filterSubmitButton
                                .removeClass('btn-primary')
                                .addClass('disabled')
                                .prop('disabled', true);

                        }, 10);
                    } else {
                        self.standardReport.filterSubmitButton
                            .changeButtonState('reset')
                            .addClass('btn-primary')
                            .removeClass('disabled')
                            .prop('disabled', false);
                    }
                },
                error: function (data) {
                    var humanReadable;
                    self.reportRequest = null;
                    if (data.status !== 0) {
                        // If it is a BadRequest allow for report to specify text
                        if (data.status === 400) {
                            humanReadable = data.responseText || self.humanReadableErrors[data.status];
                        } else {
                            humanReadable = self.humanReadableErrors[data.status];
                        }
                        self.loadingIssueModalElem.find('.report-error-status').html('<strong>' + data.status + '</strong> ' +
                            ((humanReadable) ? humanReadable : ""));
                        if (self.issueAttempts > 0) {
                            self.loadingIssueModalElem.find('.btn-primary').changeButtonState('fail');
                        }
                        self.issueAttempts += 1;
                        self.loadingIssueModal.show();
                    } else {
                        self.hqLoading = self.reportContent.find(self.loaderClass);
                        self.hqLoading.find('h4').text(gettext("Loading Stopped"));
                        self.hqLoading.find('.js-loading-spinner').attr('style', 'visibility: hidden;');
                    }
                },
                beforeSend: function () {
                    self.standardReport.filterSubmitButton.changeButtonState('loading');
                    self.reportContent.find('.loading-backdrop').fadeIn();
                    if (self.hqLoading) {
                        self.hqLoading.attr('style', 'position: absolute; top: 30px; left: 40%;');
                        self.hqLoading.fadeIn();
                    }

                },
            });
        };

        $(document).on('click', '.try-again', function () {
            self.loadingIssueModalElem.find('.btn-primary').changeButtonState('loading');
            if (self.isCaseListRelated(window.location.pathname)) {
                self.getQueryId(window.location.search.substr(1), true, true, window.location.pathname);
            } else {
                self.updateReport(true, window.location.search.substr(1));
            }
        });

        self.loadingIssueModalElem.on('hide hide.bs.modal', function () {
            self.hqLoading = self.reportContent.find(self.loaderClass);
            self.hqLoading.find('.js-loading-spinner').addClass('d-none');
            self.hqLoading.find('h4').text(gettext('We were unsuccessful loading the report:'))
                .attr('style', 'margin-bottom: 10px;');
        });

        return self;
    };
});
