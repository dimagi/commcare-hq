import $ from 'jquery';
import ko from 'knockout';
import _ from 'underscore';
import initialPageData from 'hqwebapp/js/initial_page_data';
import 'hqwebapp/js/components/pagination';

$(function () {
    let rowData = function (data) {
        let self = {};
        self.columns = ko.observableArray(data);
        return self;
    };

    let paginationExample = function () {
        let self = {};

        self.rows = ko.observableArray();

        self.perPage = ko.observable();
        self.totalItems = ko.observable();
        self.itemsPerPage = ko.observable();

        self.showLoadingSpinner = ko.observable(true);
        self.error = ko.observable();

        self.goToPage = function (page) {
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse("styleguide_paginated_table_data"),
                data: {
                    page: page,
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.showLoadingSpinner(false);
                    self.totalItems(data.total);
                    self.rows.removeAll();
                    _.each(data.rows, function (row) {
                        self.rows.push(new rowData(row));
                    });
                    self.error(null);
                },
                error: function () {
                    self.showLoadingSpinner(false);
                    self.error(gettext("Could not load users. Please try again later or report an issue if this problem persists."));
                },
            });
        };

        // Initialize with first page of data
        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    $("#js-paginated-table-example").koApplyBindings(paginationExample());
});
