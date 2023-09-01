hqDefine("geospatial/js/gps_capture",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/components.ko", // for pagination
], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';

    var dataItemModel = function (options, dataType) {
        options = options || {};
        options = _.defaults(options, {
            name: '',
            id: '',  // Can be case_id or user_id
            lat: '',
            lon: '',
        });

        var self = ko.mapping.fromJS(options);
        self.url = ko.observable();
        if (dataType === 'user') {
            self.url(initialPageData.reverse('edit_commcare_user', options.id));
        } else {
            self.url(initialPageData.reverse('case_data', options.id));
        }

        self.onMapCaptureStart = function () {
            // TODO: Implement this function
        };

        return self;
    };

    var dataItemListModel = function () {
        var self = {};
        self.dataItems = ko.observableArray([]);  // Can be cases or users

        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.observable(0);
        self.hasUnsavedChanges = ko.observable(false);
        self.query = ko.observable('');

        self.dataType = initialPageData.get('data_type');

        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.hasError = ko.observable(false);
        self.hasSubmissionError = ko.observable(false);
        self.showTable = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError();
        });

        self.goToPage = function (pageNumber) {
            if (self.hasUnsavedChanges()) {
                const dialog = confirm(gettext(
                    "You have unsaved changes. Are you sure you would like to continue?"
                ));
                if (!dialog) {
                    return;
                }
            }
            self.dataItems.removeAll();
            self.hasError(false);
            self.hasSubmissionError(false);
            self.showPaginationSpinner(true);
            self.hasUnsavedChanges(false);
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('get_paginated_cases_or_users_without_gps'),
                data: {
                    page: pageNumber || 1,
                    limit: self.itemsPerPage(),
                    data_type: self.dataType,
                    query: self.query(),
                },
                success: function (data) {
                    self.dataItems(_.map(data.items, function (inData) {
                        return dataItemModel(inData, self.dataType);
                    }));
                    self.totalItems(data.total);

                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);

                },
                error: function (e) {
                    console.log("Error in retrieving data", e);
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.hasError(true);
                },
            });
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        self.onValueChanged = function () {
            self.hasUnsavedChanges(true);
        };

        self.onSaveClicked = function () {
            self.hasSubmissionError(false);
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse('gps_capture'),
                data: JSON.stringify({
                    'data_type': self.dataType,
                    'data_items': ko.mapping.toJS(self.dataItems()),
                }),
                dataType: "json",
                contentType: "application/json; charset=utf-8",
                success: function () {
                    location.reload();
                },
                error: function (e) {
                    self.hasSubmissionError(true);
                    console.e("Error in submission", e);
                },
            });
        };

        return self;
    };

    $(function () {
        $("#no-gps-list").koApplyBindings(dataItemListModel());
    });
});
