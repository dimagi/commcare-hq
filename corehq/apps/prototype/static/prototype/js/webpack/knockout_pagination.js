import 'commcarehq';  // IMPORTANT :: always include at beginning of any entry module

import ko from 'knockout';
import $ from 'jquery';
import _ from 'underscore';
import initialPageData from 'hqwebapp/js/initial_page_data';

import 'hqwebapp/js/components/pagination';

// The rest of the code below is otherwise the same as the core content of
// prototype/js/knockout_pagination
// ...only the imports have changed

$(function () {
    let rowData = function (data) {
        let self = {};
        self.columns = ko.observableArray(data);
        return self;
    };

    let exampleModel = function () {
        let self = {};
        self.rows = ko.observableArray();

        self.perPage = ko.observable();
        self.totalItems = ko.observable();
        self.itemsPerPage = ko.observable();

        self.error = ko.observable();

        self.goToPage = function (page) {
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse("prototype_example_paginated_data"),
                data: {
                    page: page,
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.totalItems(data.total);
                    self.rows.removeAll();
                    _.each(data.rows, function (row) {
                        self.rows.push(new rowData(row));
                    });
                    self.error(null);
                },
                error: function () {
                    self.error(gettext("Could not load data. " +
                        "Please try again later or report an issue if " +
                        "this problem persists."));
                },
            });
        };


        // Initialize with first page of data
        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    $('#prototype-example-knockout-pagination').koApplyBindings(new exampleModel());
});
