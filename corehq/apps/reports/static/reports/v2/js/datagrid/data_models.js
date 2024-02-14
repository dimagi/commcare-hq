/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/data_models', [
    'jquery',
    'knockout',
    'underscore',
    'analytix/js/kissmetrix',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/components.ko',  // pagination widget
], function (
    $,
    ko,
    _,
    kissmetrics,
    initialPageData
) {
    'use strict';

    var scrollingDataModel = function (endpoint) {
        var self = {};

        self.endpoint = endpoint;

        self.hasInitialLoadFinished = ko.observable(false);

        self.isDataLoading = ko.observable(false);
        self.isLoadingError = ko.observable(false);
        self.ajaxPromise = undefined;

        self.numTimeouts = 0;
        self.showTimeoutError = ko.observable(false);

        self.isDataLoading.subscribe(function (isLoading) {
            if (!isLoading) {
                return;
            }

            // vertically center the loading text within the table body rows,
            // and make sure the width and height of the element wrapping the
            // loading text is the same as the width and height of the rows in
            // table body
            var $rows = $('#js-datagrid-rows'),
                $loading = $('#js-datagrid-loading'),
                position = $rows.position(),
                marginTop = Math.max(0, $rows.height() / 2 - 50); // 50 is half the line height of the loading text

            if (position.top === 0) {
                return;
            }

            $loading
                .height(Math.max(100, $rows.height()))
                .width($rows.width())
                .css('left', position.left + 'px')
                .css('top', position.top + "px");
            
            $loading.find('.loading-text')
                .css('margin-top', marginTop + 'px');
        });

        self.rows = ko.observableArray([]);

        self.limit = ko.observable(undefined);
        self.hasLimitBeenModified = ko.observable(false);

        self.currentPage = ko.observable(undefined);
        self.totalRecords = ko.observable(1);

        self.resetPagination = ko.observable(false);

        self.limit.subscribe(function (newLimit) {
            // needed to stay in sync with pagination widget
            // to prevent unnecessary reloads of data
            self.hasLimitBeenModified(true);

            if (self.hasInitialLoadFinished()) {
                kissmetrics.track.event("Changed page size", {
                    "Domain": initialPageData.get('domain'),
                    "Page Size Selected": newLimit,
                });
            }
        });

        self.hasNoData = ko.computed(function () {
            return self.totalRecords() < 1;
        });

        self.goToPage = function (page) {
            if (page !== self.currentPage() || self.hasLimitBeenModified()) {
                self.currentPage(page);
                if (!self.resetPagination() || self.hasLimitBeenModified()) {
                    self.loadRecords();
                }
                self.hasLimitBeenModified(false);
                self.resetPagination(false);
            }
        };

        self.thresholds = {
            10000: "10 sec",
            20000: "20 sec",
            30000: "30 sec",
            40000: "40 sec",
            50000: "50 sec",
            60000: "1 min",
            90000: "1.5 min",
            120000: "2 min",
            300000: "5 min",
            600000: "10 min",
        };

        self.thresholdTimer = 0;
        self.thresholdInterval = 10000;

        self.sendThresholdAnalytics = setInterval(function () {
            self.thresholdTimer += self.thresholdInterval;
            if (_.has(self.thresholds, self.thresholdTimer)) {
                var eventTitle = "ECD Initial Load Threshold - " + self.thresholds[self.thresholdTimer];
                kissmetrics.track.event(eventTitle, {
                    "Domain": initialPageData.get('domain'),
                });
            }
        }, self.thresholdInterval);

        self.loadRecords = function () {
            if (!self.reportContext) {
                throw new Error("Please call init() before calling loadRecords().");
            }

            if (self.ajaxPromise) {
                self.ajaxPromise.abort();
            }

            if (self.isDataLoading()) {
                return;
            }

            // wait for pagination widget to kick in
            if (self.currentPage() === undefined) {
                return;
            }
            if (self.limit() === undefined) {
                return;
            }

            self.isLoadingError(false);
            self.isDataLoading(true);

            self.ajaxPromise = $.ajax({
                url: self.endpoint.getUrl(),
                method: 'post',
                dataType: 'json',
                data: {
                    limit: self.limit(),
                    page: self.currentPage(),
                    totalRecords: self.totalRecords(),
                    reportContext: JSON.stringify(self.reportContext()),
                },
            })
                .done(function (data) {
                    if (data.isTimeout && self.numTimeouts < 6) {
                        self.numTimeouts ++;
                        self.isDataLoading(false);
                        self.ajaxPromise = undefined;
                        self.refresh();
                        return;
                    }

                    if (data.isTimeout) {
                        self.showTimeoutError(true);
                        kissmetrics.track.event("ECD Timeout Error After 5 Attempts", {
                            "Domain": initialPageData.get('domain'),
                        });
                    } else {
                        self.showTimeoutError(false);
                        self.numTimeouts = 0;
                        var timeEventTitle = "ECD Load Time";
                        if (!self.hasInitialLoadFinished()) {
                            timeEventTitle = timeEventTitle + " - Initial";
                        }
                        kissmetrics.track.event(timeEventTitle, {
                            "Domain": initialPageData.get('domain'),
                            "Time": data.took,
                        });

                    }

                    self.rows(data.rows);
                    if (self.hasInitialLoadFinished()) {
                        self.resetPagination(data.resetPagination);
                    }
                    self.totalRecords(data.totalRecords);

                    if (!self.hasInitialLoadFinished()) {
                        self.hasInitialLoadFinished(true);
                        clearInterval(self.sendThresholdAnalytics);
                        $('#js-datagrid-initial-loading').fadeOut();
                        _.each(self.reportFilters(), function (reportFilter) {
                            reportFilter.value.subscribe(function () {
                                self.refresh();
                            });
                            reportFilter.isLoadingComplete(true);
                        });
                    }
                })
                .fail(function (e) {
                    if (e.statusText !== 'abort') {
                        self.rows([]);
                        self.isLoadingError(true);
                    }
                })
                .always(function () {
                    self.isDataLoading(false);
                    self.ajaxPromise = undefined;
                });
        };

        self.init = function (reportContextObservable, reportFiltersObservable) {
            self.reportContext = reportContextObservable;
            self.reportFilters = reportFiltersObservable;
            self.pageTitle = $(document).find("title").text();

            var _url = new URL(window.location.href);
            self.currentPage(_url.searchParams.get('p') || self.currentPage());
            self.limit(_url.searchParams.get('l') || self.limit());

        };

        self.refresh = function () {
            self.loadRecords();
        };

        return self;
    };

    return {
        scrollingDataModel: scrollingDataModel,
    };
});
