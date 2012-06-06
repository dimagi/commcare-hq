var HQAsyncReport = function (o) {
    'use strict';
    var self = this;
    self.submitButton = o.submitButton || $('#paramSelectorForm button[type="submit"]');
    self.reportContent = o.reportContent ||  $('#report-content');
    self.filterForm = o.filterForm || $('#paramSelectorForm');
    self.loadingIssueModal = o.loadingIssueModal || $('#loadingReportIssueModal');
    self.issueAttempts = 0;
    self.hqLoading = null;

    var loadFilters = function (data) {
        $('#hq-report-filters').html(data.filters);
        $('#reportFiltersAccordion').removeClass('hide');
    };

    self.init = function () {
        self.reportContent.attr('style', 'position: relative;');

        self.submitButton.addClass('disabled');
        self.filterForm.change(function () {
            self.submitButton.button('reset').addClass('btn-primary');
        });

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
        $.ajax({
            url: window.location.pathname.replace('/reports/', '/reports/async/filters/')+"?"+form_params,
            dataType: 'json',
            success: loadFilters
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

    self.updateReport = function (initial_load, params) {
        var process_filters = (initial_load) ? "hq_filters=true&": "";
        $.ajax({
            url: window.location.pathname.replace('/reports/', '/reports/async/')+"?"+process_filters+params,
            dataType: 'json',
            success: function(data) {
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

                self.submitButton.removeClass('btn-primary').button('standard');
            },
            error: function () {
                if (self.issueAttempts > 0)
                    self.loadingIssueModal.find('.btn-primary').button('fail');
                self.issueAttempts += 1;
                self.loadingIssueModal.modal('show');
            },
            beforeSend: function () {
                self.submitButton.button('loading');
                $('.loading-backdrop').fadeIn();
                if (self.hqLoading) {
                    self.hqLoading.attr('style', 'position: absolute; top: 30px; left: 40%;');
                    self.hqLoading.fadeIn();
                }

            }
        });
    };
};