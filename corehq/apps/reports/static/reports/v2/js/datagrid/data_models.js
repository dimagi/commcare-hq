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

        self.isDataLoading = ko.observable(false);
        self.isLoadingError = ko.observable(false);

        self.isDataLoading.subscribe(function (isLoading) {
            if (!isLoading) return;

            var $rows = $('#js-datagrid-rows'),
                $loading = $('#js-datagrid-loading'),
                position = $rows.position(),
                marginTop = $rows.height()/2 - 50;

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

        self.goToPage = function (page) {
            if (page !== self.currentPage() || self.hasLimitBeenModified()) {
                self.currentPage(page);
                self.hasLimitBeenModified(false);
                if (!self.resetPagination()) {
                    self.loadRecords();
                }
                self.resetPagination(false);
            }
        };

        self._pushState = function () {
            var stateInfo = {
                    page: self.currentPage(),
                    limit: self.limit(),
                },
                url = '?p=' + self.currentPage() + "&l=" + self.limit();
            window.history.pushState(stateInfo, self.pageTitle, url);
        };

        self.loadRecords = function () {
            if (!self.reportContext) {
                throw new Error("Please call init() before calling loadRecords().");
            }

            if (self.isDataLoading()) return;

            // wait for pagination widget to kick in
            if (self.currentPage() === undefined) return;
            if (self.limit() === undefined) return;

            self.isDataLoading(true);
            $.ajax({
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
