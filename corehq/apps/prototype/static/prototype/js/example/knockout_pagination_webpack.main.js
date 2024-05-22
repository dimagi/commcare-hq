// base level imports need to figure out how to always include these

//need to figure out gettext mapping
import 'hqwebapp/js/bootstrap5/common';
import 'hqwebapp/js/bootstrap5/base_main';

import ko from 'knockout';
import mapping from 'ko.mapping';
ko.mapping = mapping;


import $ from 'jquery';
import _ from 'underscore';
import initialPageData from 'hqwebapp/js/initial_page_data';

// import 'hqwebapp/js/bootstrap5/hq.helpers';  // for using $.koApplyBindings
import 'hqwebapp/js/bootstrap5/components.ko';  // for pagination

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
