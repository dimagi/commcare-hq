hqDefine("geospatial/js/gps_capture",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/bootstrap3/components.ko", // for pagination
    'select2/dist/js/select2.full.min',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';
    const MAP_CONTAINER_ID = "geospatial-map";
    const USERS_PER_PAGE = 10;

    var map;
    var selectedDataListObject;
    var mapMarker = new mapboxgl.Marker({  // eslint-disable-line no-undef
        draggable: true,
    });
    mapMarker.on('dragend', function () {
        let lngLat = mapMarker.getLngLat();
        updateSelectedItemLonLat(lngLat.lng, lngLat.lat);
    });

    function toggleMapVisible(isVisible) {
        if (isVisible) {
            $("#" + MAP_CONTAINER_ID).show();
            centerMapWithMarker();
        } else {
            $("#" + MAP_CONTAINER_ID).hide();
        }
    }

    function centerMapWithMarker() {
        if (selectedDataListObject) {
            let dataItem = selectedDataListObject.itemLocationBeingCapturedOnMap();
            if (dataItem.lon() && dataItem.lat()) {
                map.setCenter([dataItem.lon(), dataItem.lat()]);
                setMarkerAtLngLat(dataItem.lon(), dataItem.lat());
            }
        }
    }

    function resetMap() {
        toggleMapVisible(false);
        if (selectedDataListObject) {
            selectedDataListObject.itemLocationBeingCapturedOnMap(null);
        }
        if (mapMarker) {
            mapMarker.remove();
        }
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

        self.isCreatingCase = ko.observable(false);
        self.hasCreateCaseError = ko.observable(false);
        self.availableCaseTypes = ko.observableArray([]);
        self.selectedCaseType = ko.observable('');
        self.hasCaseTypeError = ko.observable(false);
        self.selectedOwnerId = ko.observable(null);

        self.captureLocationForItem = function (item) {
            self.itemLocationBeingCapturedOnMap(item);
            selectedDataListObject = self;
            toggleMapVisible(true);
        };
        self.setCoordinates = function (lat, lng) {
            self.itemLocationBeingCapturedOnMap().setCoordinates(lat, lng);
        };

        self.goToPage = function (pageNumber) {
            self.dataItems.removeAll();
            self.hasError(false);
            self.showPaginationSpinner(true);
            self.showLoadingSpinner(true);
            let url = initialPageData.reverse('get_paginated_cases_or_users');
            if (self.dataType === 'case') {
                url += window.location.search;
            }
            $.ajax({
                method: 'GET',
                url: url,
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

        self.onOwnerIdChange = function (_, e) {
            self.selectedOwnerId($(e.currentTarget).select2('val'));
        };

        self.saveDataRow = function (dataItem) {
            self.isSubmissionSuccess(false);
            self.hasSubmissionError(false);
            let dataItemJson = ko.mapping.toJS(dataItem);
            if (self.isCreatingCase()) {
                dataItemJson['case_type'] = self.selectedCaseType();
                dataItemJson['owner_id'] = self.selectedOwnerId();
            }

            $.ajax({
                method: 'POST',
                url: initialPageData.reverse('gps_capture'),
                data: JSON.stringify({
                    'data_type': self.dataType,
                    'data_item': dataItemJson,
                    'create_case': self.isCreatingCase(),
                }),
                dataType: "json",
                contentType: "application/json; charset=utf-8",
                success: function () {
                    dataItem.hasUnsavedChanges(false);
                    self.isSubmissionSuccess(true);
                    resetMap();
                    self.resetCaseCreate();
                    $(window).scrollTop(0);
                },
                error: function () {
                    self.hasSubmissionError(true);
                },
            });
        };

        self.startCreateCase = function () {
            self.isCreatingCase(true);
            const caseToCreate = new dataItemModel(null, self.dataType);
            self.captureLocationForItem(caseToCreate);

            const placeholderStr = `${initialPageData.get('couch_user_username')} (${gettext("current user")})`;
            $("#owner-select").select2({
                placeholder: placeholderStr,
                cache: true,
                allowClear: true,
                delay: 250,
                ajax: {
                    url: initialPageData.reverse('paginate_mobile_workers'),
                    dataType: 'json',
                    data: function (params) {
                        return {
                            query: params.term,
                            page_limit: USERS_PER_PAGE,
                            page: params.page,
                        };
                    },
                    processResults: function (data, params) {
                        params.page = params.page || 1;

                        const hasMore = (params.page * USERS_PER_PAGE) < data.total;
                        const dataResults = $.map(data.users, function (user) {
                            return {
                                text: user.username,
                                id: user.user_id,
                            };
                        });

                        return {
                            results: dataResults,
                            pagination: {
                                more: hasMore,
                            },
                        };
                    },
                },
            });
        };

        self.finishCreateCase = function () {
            const hasValidName = self.itemLocationBeingCapturedOnMap().name().length > 0;
            self.hasCreateCaseError(!hasValidName);
            const hasValidCaseType = self.selectedCaseType() && self.selectedCaseType().length > 0;
            self.hasCaseTypeError(!hasValidCaseType);
            if (hasValidName && hasValidCaseType) {
                self.saveDataRow(self.itemLocationBeingCapturedOnMap());
            }
        };

        self.cancelCreateCase = function () {
            self.resetCaseCreate();
            resetMap();
        };

        self.resetCaseCreate = function () {
            self.isCreatingCase(false);
            self.hasCreateCaseError(false);
            self.hasCaseTypeError(false);
            self.selectedCaseType('');
            self.selectedOwnerId(null);
        };

        return self;
    };

    function setMarkerAtLngLat(lon, lat) {
        mapMarker.remove();
        mapMarker.setLngLat([lon, lat]);
        mapMarker.addTo(map);
    }

    function updateSelectedItemLonLat(lon, lat) {
        selectedDataListObject.setCoordinates(lat, lon);
    }

    function updateGPSCoordinates(lon, lat) {
        setMarkerAtLngLat(lon, lat);
        updateSelectedItemLonLat(lon, lat);
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

        map.addControl(
            new MapboxGeocoder({  // eslint-disable-line no-undef
                accessToken: mapboxgl.accessToken,  // eslint-disable-line no-undef
                mapboxgl: map,
                types: 'address',
                proximity: centerCoordinates.toString(),  // bias results to this point
                marker: false,
            }).on('result', function (resultObject) {
                updateGPSCoordinates(resultObject.result.center[0], resultObject.result.center[1]);
            })
        );

        map.on('click', (event) => {
            updateGPSCoordinates(event.lngLat.lng, event.lngLat.lat);
        });
        toggleMapVisible(false);

        return map;
    };

    function TabListViewModel() {
        var self = {};
        self.onclickAction = function () {
            resetMap();
        };
        return self;
    }

    $(function () {
        const caseDataItemListInstance = dataItemListModel('case');
        caseDataItemListInstance.availableCaseTypes(initialPageData.get('case_types_with_gps'));

        $("#tabs-list").koApplyBindings(TabListViewModel());
        $("#no-gps-list-case").koApplyBindings(caseDataItemListInstance);
        $("#no-gps-list-user").koApplyBindings(dataItemListModel('user'));

        initMap();
    });
});
