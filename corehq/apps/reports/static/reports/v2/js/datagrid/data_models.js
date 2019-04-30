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

    var scrollingDataModel = function (endpoint) {
        var self = {};

        self.endpoint = endpoint;

        self.isDataLoading = ko.observable(false);
        self.isLoadingError = ko.observable(false);

        self.rows = ko.observableArray([]);
        self.length = 50; // todo change number dynamically?

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
                    length: self.length,
                    start: 0, // fix with pagination
                    reportContext: JSON.stringify(self.reportContext()),
                },
            })
                .done(function (data) {
                    self.rows(data.rows);
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
