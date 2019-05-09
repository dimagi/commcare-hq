/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/data_models', [
    'jquery',
    'knockout',
    'underscore',
], function (
    $,
    ko,
    _
) {
    'use strict';

    var _numberOption = function (number, current) {
        var self = {};

        self.number = ko.observable(number);
        self.isCurrent = ko.computed(function () {
            return self.number() === current;
        });

        return self;
    };

    var scrollingDataModel = function (endpoint) {
        var self = {};

        self.endpoint = endpoint;

        self.isDataLoading = ko.observable(false);
        self.isLoadingError = ko.observable(false);

        self.rows = ko.observableArray([]);
        self.limit = ko.observable(10);
        self.currentPage = ko.observable(1);
        self.totalPages = ko.observable(1);
        self.totalRecords = ko.observable(1);

        self.pages = ko.computed(function () {
            return _.map(_.range(1, self.totalPages() + 1), function (pageNum) {
               return _numberOption(pageNum, self.currentPage());
            });
        });

        self.limits = ko.computed(function() {
            return _.map([10, 25, 50, 100], function (limitNum) {
                return _numberOption(limitNum, self.limit());
            });
        });

        self.changePage = function (page) {
            self.currentPage(page.number());
            self.loadRecords();
        };

        self.changeLimit = function (limit) {
            self.limit(limit.number());
            self.currentPage(1);
            self.loadRecords();
        };

        self._pushState = function () {
            var stateInfo = {
                    page: self.currentPage(),
                    limit: self.limit(),
                },
                url = '?p=' + self.currentPage() + "&l=" + self.limit();
            window.history.pushState(stateInfo, self.pageTitle, url);
        };

        self._loadState = function () {
            var history = window.history.state;
            if (_.isObject(history)) {
                self.currentPage(history.page || 1);
                self.limit(history.limit || 10);
            }
        };

        self.showNext = ko.computed(function () {
           return self.currentPage() < self.totalPages();
        });

        self.showPrevious = ko.computed(function () {
            return self.currentPage() > 1;
        });

        self.nextPage = function () {
           self.currentPage(Math.min(self.totalPages(), self.currentPage() + 1));
           self.loadRecords();
        };

        self.previousPage = function () {
            self.currentPage(Math.max(self.currentPage() - 1, 1));
            self.loadRecords();
        };

        self.loadRecords = function () {
            if (!self.reportContext) {
                throw new Error("Please call init() before calling loadRecords().");
            }

            if (self.isDataLoading()) return;

            self.isDataLoading(true);
            $.ajax({
                url: self.endpoint.getUrl(),
                method: 'post',
                dataType: 'json',
                data: {
                    limit: self.limit(),
                    page: self.currentPage(),
                    reportContext: JSON.stringify(self.reportContext()),
                },
            })
                .done(function (data) {
                    self.rows(data.rows);
                    self.totalPages(data.totalPages);
                    self.totalRecords(data.totalRecords);
                    self._pushState();
                })
                .fail(function () {
                    self.isLoadingError(true);
                })
                .always(function () {
                    self.isDataLoading(false);
                });
        };

        self.init = function (reportContextObservable) {
            self.reportContext = reportContextObservable;
            self.pageTitle = $(document).find("title").text();
            self._loadState();
            self.loadRecords();
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
