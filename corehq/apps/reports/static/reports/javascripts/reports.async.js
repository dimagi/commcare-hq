var HQAsyncReport = function (o) {
    'use strict';
    var self = this;
    self.reportContent = o.reportContent ||  $('#report-content');
    self.filterForm = o.filterForm || $('#paramSelectorForm');
    self.loadingIssueModal = o.loadingIssueModal || $('#loadingReportIssueModal');
    self.issueAttempts = 0;
    self.hqLoading = null;
    self.standardReport = o.standardReport;
    self.filterRequest = null;
    self.reportRequest = null;

    self.humanReadableErrors = {
        400: "Please check your Internet connection!",
        404: "Report Not Found.",
        408: "Request timed out when rendering this report. This might be an issue with our servers"+
            " or with your Internet connection. We encourage you to report an issue to CommCare HQ Support so we"+
            " can look into any possible issues.",
        500: "Problem Rendering Report. Our error monitoring tools have noticed this and we are working quickly to" +
            " resolve this issue as soon as possible. We encourage you to contact CommCare HQ Support" +
            " if this issue persists for more than a few minutes. We appreciate any additional information" +
            " you can give us about this problem so we can fix it immediately.",
        502: "Bad Gateway. Please contact CommCare HQ Support.",
        503: "CommCare HQ is experiencing server difficulties. We're working quickly to resolve it."+
            " Thank you for your patience. We are extremely sorry.",
        504: "Gateway Timeout. Please contact CommCare HQ Support."
    };


    var loadFilters = function (data) {
        self.filterRequest = null;
        $('#hq-report-filters').html(data.filters);
        $('#reportFiltersAccordion').removeClass('hide');
        self.standardReport.resetFilterState();
    };

    self.init = function () {
        self.reportContent.attr('style', 'position: relative;');
        self.standardReport.filterSubmitButton.addClass('disabled');

        self.updateReport(true, window.location.search.substr(1));

        self.filterForm.submit(function () {
            var params = $(this).serialize();
            History.pushState(null,window.location.title,window.location.pathname+"?"+params);
            self.updateFilters(params);
            self.updateReport(false, params);
            return false;
        });

    };

    self.updateFilters = function (form_params) {
        self.standardReport.saveDatespanToCookie();
        self.filterRequest = $.ajax({
            url: window.location.pathname.replace(self.standardReport.urlRoot,
                self.standardReport.urlRoot+'filters/')+"?"+form_params,
            dataType: 'json',
            success: loadFilters
        });
    };



    self.updateReport = function (initial_load, params) {
        var process_filters = "";
        if (initial_load) {
            process_filters = "hq_filters=true&";
            if (self.standardReport.loadDatespanFromCookie()) {
                process_filters = process_filters+
                    "&startdate="+self.standardReport.datespan.startdate+
                    "&enddate="+self.standardReport.datespan.enddate;
            }
        }

        self.reportRequest = $.ajax({
            url: window.location.pathname.replace(self.standardReport.urlRoot,
                self.standardReport.urlRoot+'async/')+"?"+process_filters+"&"+params,
            dataType: 'json',
            success: function(data) {
                self.reportRequest = null;
                if (data.filters)
                    loadFilters(data);
                self.issueAttempts = 0;
                self.loadingIssueModal.modal('hide');
                self.hqLoading = $('.hq-loading');
                self.reportContent.html(data.report);
                self.reportContent.append(self.hqLoading);
                self.hqLoading.removeClass('hide');

                $('.hq-report-time-notice').removeClass('hide');

                $('.loading-backdrop').fadeOut();
                self.hqLoading.fadeOut();

                self.standardReport.filterSubmitButton.removeClass('btn-primary').button('standard');
            },
            error: function (data) {
                self.reportRequest = null;
                if (data.status != 0) {
                    var humanReadable = self.humanReadableErrors[data.status];
                    self.loadingIssueModal.find('.report-error-status').html('<strong>'+data.status+'</strong> ' +
                        ((humanReadable) ? humanReadable : ""));
                    if (self.issueAttempts > 0)
                        self.loadingIssueModal.find('.btn-primary').button('fail');
                    self.issueAttempts += 1;
                    self.loadingIssueModal.modal('show');
                } else {
                    self.hqLoading = $('.hq-loading');
                    self.hqLoading.find('h4').text("Loading Stopped");
                    self.hqLoading.find('img').attr('style', 'visibility: hidden;');
                }
            },
            beforeSend: function () {
                self.standardReport.filterSubmitButton.button('loading');
                $('.loading-backdrop').fadeIn();
                if (self.hqLoading) {
                    self.hqLoading.attr('style', 'position: absolute; top: 30px; left: 40%;');
                    self.hqLoading.fadeIn();
                }

            }
        });
    };

    self.loadingIssueModal.on('reloadHQReport', function () {
        self.loadingIssueModal.find('.btn-primary').button('loading');
        self.updateReport(true, window.location.search.substr(1));
    });

    self.loadingIssueModal.on('hide', function () {
        if (self.issueAttempts > 0) {
            self.hqLoading = $('.hq-loading');
            self.hqLoading.find('img').addClass('hide');
            self.hqLoading.find('h4').text('We were unsuccessful loading the report:').attr('style', 'margin-bottom: 10px;');
        }
    });


};