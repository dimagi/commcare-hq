hqDefine("geospatial/js/gps_capture",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/bootstrap3/components.ko", // for pagination
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
        self.dataType = dataType;
        if (self.dataType === 'user') {
            self.url(initialPageData.reverse('edit_commcare_user', options.id));
        } else {
            self.url(initialPageData.reverse('case_data', options.id));
        }
        self.hasUnsavedChanges = ko.observable(false);
        self.isLatValid = ko.observable(true);
        self.isLonValid = ko.observable(true);

        self.onMapCaptureStart = function () {
            // TODO: Implement this function
        };

        self.onValueChanged = function () {
            self.hasUnsavedChanges(true);

            self.lat(self.lat().substr(0, 20));
            self.lon(self.lon().substr(0, 20));

            let latNum = parseFloat(self.lat());
            let lonNum = parseFloat(self.lon());

            // If the text is a number followed by text (e.g. 15foobar) then parseFloat() will not show as NaN
            // We need to make sure that there is no extra text after the number
            const latValidLength = (latNum.toString().length === self.lat().length);
            const lonValidLength = (lonNum.toString().length === self.lon().length);

            const latValid = (
                (!isNaN(latNum) && latValidLength && latNum >= -90 && latNum <= 90) || !self.lat().length
            );
            self.isLatValid(latValid);
            const lonValid = (
                (!isNaN(lonNum) && lonValidLength && lonNum >= -180 && lonNum <= 180) || !self.lon().length
            );
            self.isLonValid(lonValid);
        };

        self.canSaveRow = ko.computed(function () {
            const isValidInput = self.isLatValid() && self.isLonValid();
            return self.lat().length && self.lon().length && self.hasUnsavedChanges() && isValidInput;
        });

        return self;
    };

    var dataItemListModel = function () {
        var self = {};
        self.dataItems = ko.observableArray([]);  // Can be cases or users

        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.observable(0);
        self.query = ko.observable('');

        self.dataType = initialPageData.get('data_type');

        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.hasError = ko.observable(false);
        self.hasSubmissionError = ko.observable(false);
        self.isSubmissionSuccess = ko.observable(false);
        self.showTable = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError();
        });

        self.goToPage = function (pageNumber) {
            self.dataItems.removeAll();
            self.hasError(false);
            self.showPaginationSpinner(true);
            self.showLoadingSpinner(true);
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
                error: function () {
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.hasError(true);
                },
            });
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        self.saveDataRow = function (dataItem) {
            self.isSubmissionSuccess(false);
            self.hasSubmissionError(false);
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse('gps_capture'),
                data: JSON.stringify({
                    'data_type': self.dataType,
                    'data_item': ko.mapping.toJS(dataItem),
                }),
                dataType: "json",
                contentType: "application/json; charset=utf-8",
                success: function () {
                    dataItem.hasUnsavedChanges(false);
                    self.isSubmissionSuccess(true);
                },
                error: function () {
                    self.hasSubmissionError(true);
                },
            });
        };

        return self;
    };

    $(function () {
        $("#no-gps-list").koApplyBindings(dataItemListModel());
    });
});
