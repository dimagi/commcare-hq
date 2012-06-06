$(function () {

    var HQAsyncReport = function (o) {
        'use strict';
        var self = this;
        self.submitButton = o.submitButton || $('#paramSelectorForm button[type="submit"]');
        self.reportContent = o.reportContent ||  $('#report-content');
        self.filterForm = o.filterForm || $('#paramSelectorForm');
        self.hqLoading = null;

        var loadFilters = function (data) {
            $('#hq-report-filters').html(data.filters);
            $('#reportFiltersAccordion').removeClass('hide');
            self.submitButton.removeClass('btn-primary');
        };

        self.init = function () {
            self.submitButton.addClass('disabled');
            self.reportContent.attr('style', 'position: relative;');
            self.filterForm.change(function () {
                self.submitButton.addClass('btn-primary');
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

        self.updateReport = function (initial_load, params) {
            var process_filters = (initial_load) ? "hq_filters=true&": "";
            $.ajax({
                url: window.location.pathname.replace('/reports/', '/reports/async/')+"?"+process_filters+params,
                dataType: 'json',
                success: function(data) {
                    if (data.filters)
                        loadFilters(data);
                    self.hqLoading = $('.hq-loading');

                    self.reportContent.html(data.report);
                    self.reportContent.append(self.hqLoading);

                    $('.hq-report-time-notice').removeClass('hide');
                    self.submitButton.button('reset');

                    $('.loading-backdrop').fadeOut();
                    self.hqLoading.fadeOut();
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
        }
    };

    var asyncReport = new HQAsyncReport({});
    asyncReport.init();

});