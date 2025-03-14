hqDefine("geospatial/js/case_management", [
    "jquery",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "knockout",
    'geospatial/js/models',
    'geospatial/js/utils',
    'hqwebapp/js/bootstrap5/alert_user',
    'reports/js/bootstrap5/base',
    'hqwebapp/js/select2_knockout_bindings.ko',
    'commcarehq',
], function (
    $,
    _,
    initialPageData,
    ko,
    models,
    utils,
    alertUser,
) {
    const MAP_CONTAINER_ID = 'geospatial-map';
    const SHOW_USERS_QUERY_PARAM = 'show_users';
    const USER_LOCATION_ID_QUERY_PARAM = 'user_location_id';
    const USER_LOCATION_NAME_QUERY_PARAM = 'user_location_name';

    var runDisbursementUrl = initialPageData.reverse('case_disbursement');
    var disbursementRunner;

    var mapModel;
    var polygonFilterModel;
    var assignmentManagerModel;

    function showMapControls(state) {
        $("#geospatial-map").toggle(state);
        $("#case-buttons").toggle(state);
        $("#polygon-filters").toggle(state);
        $("#user-filters-panel").toggle(state);
    }

    var disbursementRunnerModel = function () {
        var self = {};

        self.isBusy = ko.observable(false);
        self.parameters = ko.observableArray([]);

        self.disbursementErrorMessage = ko.observable('');
        self.showUnassignedCasesError = ko.observable(false);

        self.setBusy = function (isBusy) {
            self.isBusy(isBusy);
            $("#hq-content *").prop("disabled", isBusy);
            if (isBusy) {
                $("#btnRunDisbursement").addClass('disabled');
            } else {
                $("#btnRunDisbursement").removeClass('disabled');
            }
        };

        self.handleDisbursementResults = function (result) {
            // Clean stale disbursement results
            mapModel.removeDisbursementLayer();

            let groupId = 0;
            mapModel.caseGroupsIndex = {};
            for (const userItem of mapModel.userMapItems()) {
                mapModel.caseGroupsIndex[userItem.itemId] = {groupId: groupId, item: userItem};
                if (!result[userItem.itemId]) {
                    groupId++;
                    continue;
                }
                mapModel.caseMapItems().forEach((caseModel) => {
                    if (result[userItem.itemId].includes(caseModel.itemId)) {
                        mapModel.caseGroupsIndex[caseModel.itemId] = {
                            groupId: groupId,
                            item: caseModel,
                            assignedUserId: userItem.itemId,
                        };
                    }
                });
                groupId += 1;
            }
            self.connectUserWithCasesOnMap();
            self.setBusy(false);
        };

        self.getCasesForDisbursement = function (cases) {
            let caseData = [];
            const hasSelectedCases = mapModel.hasSelectedCases();
            cases.forEach(function (c) {
                // Either select all if none selected, or only pick selected cases
                if (!hasSelectedCases || c.isSelected()) {
                    caseData.push({
                        id: c.itemId,
                        lon: c.coordinates.lng,
                        lat: c.coordinates.lat,
                    });
                }
            });
            return caseData;
        };

        self.runCaseDisbursementAlgorithm = function (cases, users) {
            self.setBusy(true);
            mapModel.removeDisbursementLayer();
            const caseData = self.getCasesForDisbursement(cases);

            self.setDisbursementParameters = function (parameters) {
                var parametersList = [
                    {name: gettext("Max cases per user"), value: parameters.max_cases_per_user},
                    {name: gettext("Min cases per user"), value: parameters.min_cases_per_user},
                ];

                if (parameters.max_case_distance) {
                    const maxCaseDistanceParamValue = `${parameters.max_case_distance} km`;
                    parametersList.push({name: gettext("Max distance to case"), value: maxCaseDistanceParamValue});
                }

                if (parameters.max_case_travel_time_seconds) {
                    const travelParamValue = `${parameters.max_case_travel_time_seconds / 60} ${gettext("minutes")}`;
                    parametersList.push(
                        {name: gettext("Max travel time"), value: travelParamValue},
                    );
                }

                self.parameters(parametersList);
                $('#disbursement-params').show();
            };

            const hasSelectedUsers = mapModel.hasSelectedUsers();
            let userData = [];
            users.forEach((userMapItem) => {
                // Either select all if none selected, or only pick selected users
                if (!hasSelectedUsers || userMapItem.isSelected()) {
                    userData.push({
                        id: userMapItem.itemId,
                        lon: userMapItem.coordinates.lng,
                        lat: userMapItem.coordinates.lat,
                    });
                }
            });

            $.ajax({
                type: 'post',
                url: runDisbursementUrl,
                dataType: 'json',
                data: JSON.stringify({'users': userData, "cases": caseData}),
                contentType: "application/json; charset=utf-8",
                success: function (ret) {
                    self.setDisbursementParameters(ret["parameters"]);

                    if (ret['unassigned'].length) {
                        self.showUnassignedCasesError(true);
                    }
                    if (ret['assignments']) {
                        self.handleDisbursementResults(ret['assignments']);
                    } else {
                        self.setBusy(false);
                    }
                },
                error: function () {
                    alertUser.alert_user(
                        gettext("Oops! Something went wrong! Please check that your geospatial settings are configured correctly or contact admin if the problem persists."), 'danger',
                    );
                    self.setBusy(false);
                },
            });
        };

        self.connectUserWithCasesOnMap = function () {
            let disbursementLinesSource = generateDisbursementLinesSource();
            mapModel.addDisbursementLinesLayer(disbursementLinesSource);
        };

        function generateDisbursementLinesSource() {
            let disbursementLinesSource = {
                'type': 'FeatureCollection',
                'features': [],
            };
            for (const itemId of Object.keys(mapModel.caseGroupsIndex)) {
                let element = mapModel.caseGroupsIndex[itemId];
                if ('assignedUserId' in element) {
                    let user = mapModel.caseGroupsIndex[element.assignedUserId].item;
                    const lineCoordinates = [
                        [user.coordinates.lng, user.coordinates.lat],
                        [element.item.coordinates.lng, element.item.coordinates.lat],
                    ];
                    disbursementLinesSource.features.push(
                        {
                            type: 'Feature',
                            properties: {},
                            geometry: { type: 'LineString', coordinates: lineCoordinates },
                        },
                    );
                }
            }
            return disbursementLinesSource;
        }

        return self;
    };

    function initMap() {
        mapModel = new models.Map(false, true);
        mapModel.initMap(MAP_CONTAINER_ID);

        let selectedCases = ko.computed(function () {
            return mapModel.caseMapItems().filter(function (currCase) {
                return currCase.isSelected();
            });
        });
        let selectedUsers = ko.computed(function () {
            return mapModel.userMapItems().filter(function (currUser) {
                return currUser.isSelected();
            });
        });

        ko.applyBindings({'userModels': mapModel.userMapItems, 'selectedUsers': selectedUsers}, $("#user-modals")[0]);
        ko.applyBindings({'caseModels': mapModel.caseMapItems, 'selectedCases': selectedCases}, $("#case-modals")[0]);

        mapModel.mapInstance.on("draw.update", selectMapItemsInPolygons);
        mapModel.mapInstance.on('draw.selectionchange', selectMapItemsInPolygons);
        mapModel.mapInstance.on('draw.delete', function () {
            polygonFilterModel.btnSaveDisabled(!mapModel.mapHasPolygons());
            selectMapItemsInPolygons();
        });
        mapModel.mapInstance.on('draw.create', function () {
            polygonFilterModel.btnSaveDisabled(!mapModel.mapHasPolygons());
        });
    }

    function getMapPolygons() {
        let features = mapModel.drawControls.getAll().features;
        if (polygonFilterModel.activeSavedPolygon()) {
            features = features.concat(polygonFilterModel.activeSavedPolygon().geoJson.features);
        }
        return features;
    }

    function selectMapItemsInPolygons() {
        const polygons = getMapPolygons();
        mapModel.selectAllMapItems(polygons);
    }

    function initPolygonFilters() {
        // Assumes `map` var is initialized
        const $mapControlDiv = $("#polygon-filters");
        polygonFilterModel = new models.PolygonFilter(mapModel, false, true, false);
        polygonFilterModel.loadPolygons(initialPageData.get('saved_polygons'));
        if ($mapControlDiv.length) {
            ko.cleanNode($mapControlDiv[0]);
            $mapControlDiv.koApplyBindings(polygonFilterModel);
        }

        $("#btnRunDisbursement").click(function () {
            $('#disbursement-clear-message').hide();
            if (mapModel && mapModel.mapInstance && !polygonFilterModel.btnRunDisbursementDisabled()) {
                let selectedCases = mapModel.caseMapItems();
                let selectedUsers = mapModel.userMapItems();
                if (mapModel.mapHasPolygons() || polygonFilterModel.activeSavedPolygon()) {
                    selectedCases = mapModel.caseMapItems().filter(function (caseItem) {
                        return caseItem.isSelected();
                    });
                    selectedUsers = mapModel.userMapItems().filter((userItem) => {
                        return userItem.isSelected();
                    });
                }

                // User might do polygon filtering on an area with no cases/users. We should not do
                // disbursement if this is the case
                const hasValidData = selectedCases.length && selectedUsers.length;
                if (!hasValidData) {
                    const errorMessage = gettext("Please ensure that the filtered area includes both cases " +
                                                 "and mobile workers before attempting to run disbursement.");
                    disbursementRunner.disbursementErrorMessage(errorMessage);
                } else {
                    disbursementRunner.disbursementErrorMessage('');
                    disbursementRunner.showUnassignedCasesError(false);
                }
                if (hasValidData) {
                    disbursementRunner.runCaseDisbursementAlgorithm(selectedCases, selectedUsers);
                }
            }
        });
    }

    var userFiltersModel = function () {
        var self = {};

        self.shouldShowUsers = ko.observable(false);
        self.hasFiltersChanged = ko.observable(false);  // Used to disable "Apply" button
        self.showFilterMenu = ko.observable(true);
        self.hasErrors = ko.observable(false);
        self.selectedLocation = null;

        self.setUserFiltersFromUrl = function () {
            const shouldShowUsers = utils.fetchQueryParam(SHOW_USERS_QUERY_PARAM) || false;
            self.shouldShowUsers(shouldShowUsers);
            const userLocationId = utils.fetchQueryParam(USER_LOCATION_ID_QUERY_PARAM);
            if (userLocationId) {
                self.selectedLocation = userLocationId;
                const userLocationName = utils.fetchQueryParam(USER_LOCATION_NAME_QUERY_PARAM);
                const $filterSelect = $("#location-filter-select");
                $filterSelect.append(new Option(userLocationName, self.selectedLocation));
                $filterSelect.val(self.selectedLocation).trigger('change');
                self.loadUsers();
            } else if (shouldShowUsers) {
                // If only checkbox is ticked, then load all users
                self.loadUsers();
            }
        };

        self.loadUsers = function () {
            mapModel.removeItemTypeFromSource('user');
            mapModel.userMapItems([]);
            self.hasErrors(false);
            if (!self.shouldShowUsers()) {
                self.hasFiltersChanged(false);
                return;
            }

            $.ajax({
                method: 'GET',
                data: {'location_id': self.selectedLocation},
                url: initialPageData.reverse('get_users_with_gps'),
                success: function (data) {
                    self.hasFiltersChanged(false);
                    let features = [];
                    let userMapItems = [];
                    const polygonFeatures = getMapPolygons();
                    for (const userData of data.user_data) {
                        const gpsData = (userData.gps_point) ? userData.gps_point.split(' ') : [];
                        if (!gpsData.length) {
                            continue;
                        }
                        const coordinates = {
                            'lat': gpsData[0],
                            'lng': gpsData[1],
                        };
                        const editUrl = initialPageData.reverse('edit_commcare_user', userData.id);
                        const link = `<a class="ajax_dialog" href="${editUrl}" target="_blank">${userData.username}</a>`;
                        const isInPolygon = mapModel.isMapItemInPolygons(polygonFeatures, coordinates);
                        const parsedData = {
                            id: userData.id,
                            coordinates: coordinates,
                            link: link,
                            name: userData.username,
                            itemType: 'user',
                            isSelected: isInPolygon,
                            customData: {
                                primary_loc_name: userData.primary_loc_name,
                            },
                        };

                        const userMapItem = new models.MapItem(parsedData, mapModel);
                        userMapItems.push(userMapItem);
                        features.push(userMapItem.getGeoJson());
                    }
                    mapModel.addDataToSource(features);
                    mapModel.userMapItems(userMapItems);
                },
                error: function () {
                    self.hasErrors(true);
                },
            });
        };

        self.onLocationFilterChange = function (_, e) {
            self.selectedLocation = $(e.currentTarget).select2('val');
            self.onFiltersChange();
        };

        self.onFiltersChange = function () {
            self.hasFiltersChanged(true);
            self.setLocationQueryParams();
        };

        self.setLocationQueryParams = function () {
            if (self.selectedLocation) {
                utils.setQueryParam(USER_LOCATION_ID_QUERY_PARAM, self.selectedLocation);
                const selectedLocationData = $("#location-filter-select").select2('data');
                if (selectedLocationData.length) {
                    // We shouldn't have more than 1, since this select2 doesn't have multi-select enabled
                    const userLocationName = selectedLocationData[0].text;
                    utils.setQueryParam(USER_LOCATION_NAME_QUERY_PARAM, userLocationName);
                }
            } else {
                utils.clearQueryParam(USER_LOCATION_ID_QUERY_PARAM);
                utils.clearQueryParam(USER_LOCATION_NAME_QUERY_PARAM);
            }
        };

        self.toggleFilterMenu = function () {
            self.showFilterMenu(!self.showFilterMenu());
            const shouldShow = self.showFilterMenu() ? 'show' : 'hide';
            $("#user-filters-panel .panel-body").collapse(shouldShow);
        };

        self.shouldShowUsers.subscribe(function (shouldShowUsers) {
            if (shouldShowUsers) {
                utils.setQueryParam(SHOW_USERS_QUERY_PARAM, true);
            } else {
                utils.clearQueryParam(SHOW_USERS_QUERY_PARAM);
            }
        });

        return self;
    };

    function initUserFilters() {
        const $userFiltersDiv = $("#user-filters-panel");
        if ($userFiltersDiv.length) {
            const userFiltersInstance = userFiltersModel();
            $userFiltersDiv.koApplyBindings(userFiltersInstance);
            $("#location-filter-select").select2({
                placeholder: gettext('All locations'),
                allowClear: true,
                cache: true,
                ajax: {
                    url: initialPageData.reverse('location_search'),
                    dataType: 'json',
                    processResults: function (data) {
                        return {
                            results: $.map(data.results, function (item) {
                                return {
                                    text: item.text,
                                    id: item.id,
                                };
                            }),
                        };
                    },
                },
            });
            userFiltersInstance.setUserFiltersFromUrl();
        }
    }

    function initAssignmentReview() {
        const $manageAssignmentModal = $("#assignments-results");
        if ($manageAssignmentModal.length) {
            assignmentManagerModel = models.AssignmentManager(mapModel, disbursementRunner);
            $manageAssignmentModal.koApplyBindings(assignmentManagerModel);
        }
    }

    function beforeLoadCases(caseData) {
        loadCases(caseData);
        if (mapModel.hasDisbursementLayer()) {
            mapModel.removeDisbursementLayer();
        }
    }

    function loadCases(caseData) {
        mapModel.removeItemTypeFromSource('case');
        mapModel.caseMapItems([]);
        let features = [];
        let caseMapItems = [];
        const polygonFeatures = getMapPolygons();
        for (const caseItem of caseData) {
            const isInPolygon = mapModel.isMapItemInPolygons(polygonFeatures, caseItem[1]);
            const parsedData = {
                id: caseItem[0],
                coordinates: caseItem[1],
                link: caseItem[2],
                name: caseItem[3],
                itemType: 'case',
                isSelected: isInPolygon,
                customData: {},
            };
            const caseMapItem = new models.MapItem(parsedData, mapModel);
            caseMapItems.push(caseMapItem);
            features.push(caseMapItem.getGeoJson());
        }
        mapModel.caseMapItems(caseMapItems);
        mapModel.addDataToSource(features);
        mapModel.fitMapBounds(caseMapItems);
    }

    $(document).ajaxComplete(function (event, xhr, settings) {
        // When mobile workers are loaded from the user filtering menu, ajaxComplete will be called again.
        // We don't want to reload the map or cases when this happens, so simply return.
        const isAfterUserLoad = settings.url.includes('microplanning/get_users_with_gps/');
        if (isAfterUserLoad) {
            return;
        }

        const isAfterReportLoad = settings.url.includes('microplanning/async/microplanning_map/');
        // This indicates clicking Apply button or initial page load
        if (isAfterReportLoad) {
            initMap();
            mapModel.mapInstance.on('load', () => {
                initPolygonFilters();
                initUserFilters();
                initAssignmentReview();
            });

            // Hide controls until data is displayed
            showMapControls(false);

            disbursementRunner = new disbursementRunnerModel();

            $("#disbursement-spinner").koApplyBindings(disbursementRunner);
            $("#disbursement-error").koApplyBindings(disbursementRunner);
            $("#disbursement-params").koApplyBindings(disbursementRunner);

            return;
        }

        // This indicates that report data is fetched either after apply or after pagination
        const isAfterDataLoad = settings.url.includes('microplanning/json/microplanning_map/');
        if (!isAfterDataLoad) {
            return;
        }

        showMapControls(true);
        // Hide the datatable rows but not the pagination bar
        $('.dataTables_scroll').hide();

        if (xhr.status !== 200) {
            if (xhr.responseText.length) {
                alertUser.alert_user(xhr.responseText, 'danger');
            } else {
                alertUser.alert_user(
                    gettext('Oops! Something went wrong! Please report an issue if the problem persists.'),
                    'danger',
                );
            }
        } else if (xhr.responseJSON.aaData.length && mapModel.mapInstance) {
            if (polygonFilterModel) {
                beforeLoadCases(xhr.responseJSON.aaData);
            } else {
                mapModel.mapInstance.on('load', () => {
                    beforeLoadCases(xhr.responseJSON.aaData);
                });
            }
        }
    });
});
