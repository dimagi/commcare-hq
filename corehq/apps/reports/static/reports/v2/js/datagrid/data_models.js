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
            if (self.isDataLoading()) return;

            self.isDataLoading(true);
            $.ajax({
                url: self.endpoint.getUrl(),
                method: 'post',
                dataType: 'json',
                data: {
                    length: self.length,
                    start: self.rows().length,
                },
            })
            .done(function (data) {
                self.rows(_.union(self.rows(), data.rows));
            })
            .fail(function () {
                self.isLoadingError(true);
            })
            .always(function () {
                self.isDataLoading(false);
            });
        };

        self.init = function () {
            self.loadRecords();
        };

        return self;
    };

    return {
      scrollingDataModel: scrollingDataModel,
    };
});
