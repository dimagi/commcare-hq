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
    const selectedMarkerColor = "#00FF00"; // Green

    const MAP_CONTAINER_ID = "geospatial-map";
    var map;
    var selectedDataListItem;
    var coordinateCaptureMarker;

    function setMapVisible(isVisible) {
        if (isVisible) {
            $("#" + MAP_CONTAINER_ID).show();
            centerMapWithMarker();
        } else {
            $("#" + MAP_CONTAINER_ID).hide();
        }
    }

    function centerMapWithMarker() {
        if (selectedDataListItem) {
            let dataItem = selectedDataListItem.itemLocationBeingCapturedOnMap();
            if (dataItem.lon() && dataItem.lat()) {
                map.setCenter([dataItem.lon(), dataItem.lat()]);
                setMarkerAtLngLat(dataItem.lon(), dataItem.lat());
            }
        }
    }

    function runSaveSuccessCallback() {
        setMapVisible(false);
        selectedDataListItem.itemLocationBeingCapturedOnMap(null);
        coordinateCaptureMarker = undefined;
    }

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

        self.setCoordinates = function (lat, lng) {
            self.lat(lat.toString());
            self.lon(lng.toString());
            self.onValueChanged();
        };

        self.onValueChanged = function () {
            self.hasUnsavedChanges(true);

            self.lat(self.lat().substr(0, 20));
            self.lon(self.lon().substr(0, 20));

            let latNum = parseFloat(self.lat());
            let lonNum = parseFloat(self.lon());

            // parseFloat() ignores any trailing text (e.g. 15foobar becomes 15) so we need to check for length to catch
            // and correctly validate such cases
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

    var dataItemListModel = function (dataType) {
        var self = {};
        self.dataItems = ko.observableArray([]);  // Can be cases or users

        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.observable(0);
        self.itemLocationBeingCapturedOnMap = ko.observable();
        self.query = ko.observable('');

        self.dataType = dataType;
        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.hasError = ko.observable(false);
        self.hasSubmissionError = ko.observable(false);
        self.isSubmissionSuccess = ko.observable(false);
        self.showTable = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.hasError();
        });

        self.captureLocationForItem = function (item) {
            self.itemLocationBeingCapturedOnMap(item);
            selectedDataListItem = self;
            setMapVisible(true);
        };
        self.setCoordinates = function (lat, lng) {
            self.itemLocationBeingCapturedOnMap().setCoordinates(lat, lng);
        };

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
                    runSaveSuccessCallback();
                },
                error: function () {
                    self.hasSubmissionError(true);
                },
            });
        };

        return self;
    };

    function updateSelectedItemLonLat(lon, lat) {
        selectedDataListItem.setCoordinates(lat, lon);
    }

    function onMarkerDragEnd() {
        let lngLat = coordinateCaptureMarker.getLngLat();
        updateSelectedItemLonLat(lngLat.lng, lngLat.lat);
    }

    function setMarkerAtLngLat(lon, lat) {
        if (coordinateCaptureMarker) { coordinateCaptureMarker.remove(); }

        coordinateCaptureMarker = new mapboxgl.Marker({  // eslint-disable-line
            color: selectedMarkerColor,
            draggable: true,
        });
        coordinateCaptureMarker.on('dragend', onMarkerDragEnd);
        coordinateCaptureMarker.setLngLat([lon, lat]);
        coordinateCaptureMarker.addTo(map);
    }

    var initMap = function () {
        'use strict';

        mapboxgl.accessToken = initialPageData.get('mapbox_access_token');  // eslint-disable-line no-undef

        let centerCoordinates = [2.43333330, 9.750]; // should be domain specific

        map = new mapboxgl.Map({  // eslint-disable-line no-undef
            container: MAP_CONTAINER_ID, // container ID
            style: 'mapbox://styles/mapbox/streets-v12', // style URL
            center: centerCoordinates, // starting position [lng, lat]
            zoom: 6,
            attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                         ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        });

        map.on('click', (event) => {
            setMarkerAtLngLat(event.lngLat.lng, event.lngLat.lat);
            updateSelectedItemLonLat(event.lngLat.lng, event.lngLat.lat);
        });
        setMapVisible(false);
        return map;
    };

    $(function () {
        $("#no-gps-list-case").koApplyBindings(dataItemListModel('case'));
        $("#no-gps-list-user").koApplyBindings(dataItemListModel('user'));

        initMap();
    });
});
