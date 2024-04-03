hqDefine("reports/js/bootstrap5/reports.async", function () {
    return function (o) {
        'use strict';
        var self = {};
        self.reportContent = $('#report-content');
        self.filterForm = o.filterForm || $('#paramSelectorForm');
        self.loadingIssueModal = $('#loadingReportIssueModal');
        self.issueAttempts = 0;
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
                $('#hq-report-filters').html(data.filters);
                hqImport("reports/js/filters/bootstrap3/main").init();
            } catch (e) {
                console.log(e);
            }
            $('#reportFiltersAccordion').removeClass('hide');
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
                var params = hqImport('reports/js/reports.util').urlSerialize(this);
                if (self.isCaseListRelated(pathName)) {
                    var url = window.location.href.replace(self.standardReport.urlRoot,
                        self.standardReport.urlRoot + 'async/') + "?" + "&" + params;
                    if (url.length > self.maxInputLimit) {
                        hqImport('hqwebapp/js/bootstrap3/alert_user').alert_user(self.humanReadableErrors['maxInputError'], "danger");
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
                url: pathName.replace(self.standardReport.urlRoot, self.standardReport.urlRoot + 'get_or_create_hash/'),
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
                url: window.location.pathname.replace(self.standardReport.urlRoot,
                    self.standardReport.urlRoot + 'filters/') + "?" + params,
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
                $(self.standardReport.exportReportButton).removeClass('hide');
                $(self.standardReport.emailReportButton).removeClass('hide');
                $(self.standardReport.printReportButton).removeClass('hide');
            }

            self.reportRequest = $.ajax({
                url: (window.location.pathname.replace(self.standardReport.urlRoot,
                    self.standardReport.urlRoot + 'async/')) + "?" + processFilters + "&" + params,
                dataType: 'json',
                success: function (data) {
                    self.reportRequest = null;
                    if (data.filters) {
                        loadFilters(data);
                    }
                    self.issueAttempts = 0;
                    if ($('loadingIssueModal').hasClass('show')) {
                        self.loadingIssueModal.modal('hide');
                    }
                    self.hqLoading = $(self.loaderClass);
                    self.reportContent.html(data.report);
                    hqImport('reports/js/charts/main').init();
                    // clear lingering popovers
                    _.each($('body > .popover'), function (popover) {
                        $(popover).remove();
                    });
                    self.reportContent.append(self.hqLoading);
                    self.hqLoading.removeClass('hide');

                    // Assorted UI cleanup/initialization
                    $('.hq-report-time-notice').removeClass('hide');
                    if ($.timeago) {
                        $(".timeago").timeago();
                    }

                    $('.loading-backdrop').fadeOut();
                    self.hqLoading.fadeOut();

                    if (!initialLoad || !self.standardReport.needsFilters) {
                        self.standardReport.filterSubmitButton
                            .button('reset');
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
                            .button('reset')
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
                        self.loadingIssueModal.find('.report-error-status').html('<strong>' + data.status + '</strong> ' +
                            ((humanReadable) ? humanReadable : ""));
                        if (self.issueAttempts > 0) {
                            self.loadingIssueModal.find('.btn-primary').button('fail');
                        }
                        self.issueAttempts += 1;
                        self.loadingIssueModal.modal('show');
                    } else {
                        self.hqLoading = $(self.loaderClass);
                        self.hqLoading.find('h4').text(gettext("Loading Stopped"));
                        self.hqLoading.find('.js-loading-spinner').attr('style', 'visibility: hidden;');
                    }
                },
                beforeSend: function () {
                    self.standardReport.filterSubmitButton.button('loading');
                    $('.loading-backdrop').fadeIn();
                    if (self.hqLoading) {
                        self.hqLoading.attr('style', 'position: absolute; top: 30px; left: 40%;');
                        self.hqLoading.fadeIn();
                    }

                },
            });
        };

        $(document).on('click', '.try-again', function () {
            self.loadingIssueModal.find('.btn-primary').button('loading');
            if (self.isCaseListRelated(window.location.pathname)) {
                self.getQueryId(window.location.search.substr(1), true, true, window.location.pathname);
            } else {
                self.updateReport(true, window.location.search.substr(1));
            }
        });

        self.loadingIssueModal.on('hide hide.bs.modal', function () {
            self.hqLoading = $(self.loaderClass);
            self.hqLoading.find('.js-loading-spinner').addClass('hide');
            self.hqLoading.find('h4').text(gettext('We were unsuccessful loading the report:'))
                .attr('style', 'margin-bottom: 10px;');
        });

        return self;
    };
});
