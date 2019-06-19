/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/data_models', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/components.ko',  // pagination widget
], function (
    $,
    ko,
    _
) {
    'use strict';

    var scrollingDataModel = function (endpoint) {
        var self = {};

        self.endpoint = endpoint;

        self.hasInitialLoadFinished = ko.observable(false);

        self.isDataLoading = ko.observable(false);
        self.isLoadingError = ko.observable(false);
        self.ajaxPromise = undefined;

        self.isDataLoading.subscribe(function (isLoading) {
            if (!isLoading) return;

            // vertically center the loading text within the table body rows,
            // and make sure the width and height of the element wrapping the
            // loading text is the same as the width and height of the rows in
            // table body
            var $rows = $('#js-datagrid-rows'),
                $loading = $('#js-datagrid-loading'),
                position = $rows.position(),
                marginTop = $rows.height() / 2 - 50; // 50 is half the line height of the loading text

            if (position.top === 0) return;

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

        self.limit.subscribe(function () {
            // needed to stay in sync with pagination widget
            // to prevent unnecessary reloads of data
            self.hasLimitBeenModified(true);
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

        self.loadRecords = function () {
            if (!self.reportContext) {
                throw new Error("Please call init() before calling loadRecords().");
            }

            if (self.ajaxPromise) {
                self.ajaxPromise.abort();
            }

            if (self.isDataLoading()) return;

            // wait for pagination widget to kick in
            if (self.currentPage() === undefined) return;
            if (self.limit() === undefined) return;

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
                    self.resetPagination(data.resetPagination);
                    self.rows(data.rows);
                    self.totalRecords(data.totalRecords);

                    if (!self.hasInitialLoadFinished()) {
                        self.hasInitialLoadFinished(true);
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
