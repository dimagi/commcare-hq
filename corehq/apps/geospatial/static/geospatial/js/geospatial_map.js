hqDefine("geospatial/js/geospatial_map", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "knockout",
    'select2/dist/js/select2.full.min',
], function (
    $,
    initialPageData,
    ko
) {
    const caseMarkerColors = {
        'default': "#808080", // Gray
        'selected': "#00FF00", // Green
    };
    const userMarkerColors = {
        'default': "#0e00ff", // Blue
        'selected': "#0b940d", // Dark Green
    };
    const DEFAULT_POLL_TIME_MS = 1500;

    var saveGeoJSONUrl = initialPageData.reverse('geo_polygon');
    var runDisbursementUrl = initialPageData.reverse('case_disbursement');
    var disbursementRunner;
    var caseGroupsIndex = {};


    function showMapControls(state) {
        $("#geospatial-map").toggle(state);
        $("#case-buttons").toggle(state);
        $("#mapControls").toggle(state);
        $("#user-filters-panel").toggle(state);
    }

    $(function () {
        var saveGeoJson = function (drawInstance, mapControlsModelInstance) {
            var data = drawInstance.getAll();

            if (data.features.length) {
                let name = window.prompt(gettext("Name of the Area"));
                data['name'] = name;

                $.ajax({
                    type: 'post',
                    url: saveGeoJSONUrl,
                    dataType: 'json',
                    data: JSON.stringify({'geo_json': data}),
                    contentType: "application/json; charset=utf-8",
                    success: function (ret) {
                        delete data.name;
                        // delete drawn area
                        drawInstance.deleteAll();
                        mapControlsModelInstance.savedPolygons.push(
                            savedPolygon({
                                name: name,
                                id: ret.id,
                                geo_json: data,
                            })
                        );
                        // redraw using mapControlsModelInstance
                        mapControlsModelInstance.selectedPolygon(ret.id);
                    },
                });
            }
        };

        function connectUserWithCasesOnMap(user, cases) {
            cases.forEach((caseModel) => {
                const lineCoordinates = [
                    [user.itemData.coordinates.lng, user.itemData.coordinates.lat],
                    [caseModel.itemData.coordinates.lng, caseModel.itemData.coordinates.lat],
                ];
                let mapInstance = map.getMapboxInstance();
                mapInstance.addLayer({
                    id: getLineFeatureId(caseModel.itemId),
                    type: 'line',
                    source: {
                        type: 'geojson',
                        data: {
                            type: 'Feature',
                            properties: {},
                            geometry: {
                                type: 'LineString',
                                coordinates: lineCoordinates,
                            },
                        },
                    },
                    layout: {
                        'line-join': 'round',
                        'line-cap': 'round',
                    },
                    paint: {
                        'line-color': '#808080',
                        'line-width': 1,
                    },
                });
            });
        }

        var disbursementRunnerModel = function () {
            var self = {};

            self.pollUrl = ko.observable('');
            self.isBusy = ko.observable(false);

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
                var groupId = 0;
                Object.keys(result).forEach((userId) => {
                    let user = userModels().find((userModel) => {return userModel.itemId === userId;});
                    const userCoordString = user.itemData.coordinates['lng'] + " " + user.itemData.coordinates['lat'];
                    caseGroupsIndex[userCoordString] = {groupId: groupId, item: user};

                    let cases = [];
                    caseModels().forEach((caseModel) => {
                        if (result[userId].includes(caseModel.itemId)) {
                            cases.push(caseModel);
                            const coordString = caseModel.itemData.coordinates['lng'] + " " + caseModel.itemData.coordinates['lat'];
                            caseGroupsIndex[coordString] = {groupId: groupId, item: caseModel};
                        }
                    });
                    connectUserWithCasesOnMap(user, cases);
                    groupId += 1;
                });
                self.setBusy(false);
            };

            self.runCaseDisbursementAlgorithm = function (cases, users) {
                self.setBusy(true);
                let mapInstance = map.getMapboxInstance();

                let caseData = [];
                cases.forEach(function (c) {
                    const layerId = getLineFeatureId(c.itemId);
                    if (mapInstance.getLayer(layerId)) {
                        mapInstance.removeLayer(layerId);
                    }
                    if (mapInstance.getSource(layerId)) {
                        mapInstance.removeSource(layerId);
                    }

                    caseData.push({
                        id: c.itemId,
                        lon: c.itemData.coordinates.lng,
                        lat: c.itemData.coordinates.lat,
                    });
                });

                let userData = users.map(function (c) {
                    return {
                        id: c.itemId,
                        lon: c.itemData.coordinates.lng,
                        lat: c.itemData.coordinates.lat,
                    };
                });

                $.ajax({
                    type: 'post',
                    url: runDisbursementUrl,
                    dataType: 'json',
                    data: JSON.stringify({'users': userData, "cases": caseData}),
                    contentType: "application/json; charset=utf-8",
                    success: function (ret) {
                        if (ret['poll_url'] !== undefined) {
                            self.startPoll(ret['poll_url']);
                        } else {
                            self.handleDisbursementResults(ret['result']);
                        }
                    },
                });
            };

            self.startPoll = function (pollUrl) {
                if (!self.isBusy()) {
                    self.setBusy(true);
                }
                self.pollUrl(pollUrl);
                self.doPoll();
            };

            self.doPoll = function () {
                var tick = function () {
                    $.ajax({
                        method: 'GET',
                        url: self.pollUrl(),
                        success: function (data) {
                            const result = data.result;
                            if (!data) {
                                setTimeout(tick, DEFAULT_POLL_TIME_MS);
                            } else {
                                self.handleDisbursementResults(result);
                            }
                        },
                    });
                };
                tick();
            };

            return self;
        };

        var userFiltersModel = function () {
            var self = {};

            self.shouldShowUsers = ko.observable(false);
            self.hasFiltersChanged = ko.observable(false);  // Used to disable "Apply" button
            self.showFilterMenu = ko.observable(true);
            self.hasErrors = ko.observable(false);
            self.selectedLocation = null;

            self.loadUsers = function () {
                map.removeMarkersFromMap(userModels());
                userModels([]);
                self.hasErrors(false);
                if (!self.shouldShowUsers()) {
                    self.hasFiltersChanged(false);
                    missingGPSModelInstance.usersWithoutGPS([]);
                    return;
                }

                $.ajax({
                    method: 'GET',
                    data: {'location_id': self.selectedLocation},
                    url: initialPageData.reverse('get_users_with_gps'),
                    success: function (data) {
                        self.hasFiltersChanged(false);

                        // TODO: There is a lot of indexing happening here. This should be replaced with a mapping to make reading it more explicit
                        const usersWithoutGPS = data.user_data.filter(function (item) {
                            return item.gps_point === null || !item.gps_point.length;
                        });
                        missingGPSModelInstance.usersWithoutGPS(usersWithoutGPS);

                        const usersWithGPS = data.user_data.filter(function (item) {
                            return item.gps_point !== null && item.gps_point.length;
                        });

                        const userData = _.object(_.map(usersWithGPS, function (userData) {
                            const gpsData = (userData.gps_point) ? userData.gps_point.split(' ') : [];
                            const lat = parseFloat(gpsData[0]);
                            const lng = parseFloat(gpsData[1]);

                            const editUrl = initialPageData.reverse('edit_commcare_user', userData.id);
                            const link = `<a class="ajax_dialog" href="${editUrl}" target="_blank">${userData.username}</a>`;

                            return [userData.id, {'coordinates': {'lat': lat, 'lng': lng}, 'link': link, 'type': 'user'}];
                        }));

                        const userMapItems = map.addMarkersToMap(userData, userMarkerColors);
                        userModels(userMapItems);
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
            };

            self.toggleFilterMenu = function () {
                self.showFilterMenu(!self.showFilterMenu());
                const shouldShow = self.showFilterMenu() ? 'show' : 'hide';
                $("#user-filters-panel .panel-body").collapse(shouldShow);
            };

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
            }
        }

        function loadCases(caseData) {
            map.removeMarkersFromMap(caseModels());
            caseModels([]);
            var casesWithGPS = caseData.filter(function (item) {
                return item[1] !== null;
            });
            // Index by case_id
            var casesById = _.object(_.map(casesWithGPS, function (item) {
                if (item[1]) {
                    return [item[0], {'coordinates': item[1], 'link': item[2], 'type': 'case'}];
                }
            }));
            const caseMapItems = map.addMarkersToMap(casesById, caseMarkerColors);
            caseModels(caseMapItems);

            var $missingCasesDiv = $("#missing-gps-cases");
            var casesWithoutGPS = caseData.filter(function (item) {
                return item[1] === null;
            });
            casesWithoutGPS = _.map(casesWithoutGPS, function (item) {return {"link": item[2]};});
            // Don't re-apply if this is the next page of the pagination
            if (ko.dataFor($missingCasesDiv[0]) === undefined) {
                $missingCasesDiv.koApplyBindings(missingGPSModelInstance);
                missingGPSModelInstance.casesWithoutGPS(casesWithoutGPS);
            }
            missingGPSModelInstance.casesWithoutGPS(casesWithoutGPS);

            fitMapBounds(caseMapItems);
        }

        $(document).ajaxComplete(function (event, xhr, settings) {
            // When mobile workers are loaded from the user filtering menu, ajaxComplete will be called again.
            // We don't want to reload the map or cases when this happens, so simply return.
            const isAfterUserLoad = settings.url.includes('geospatial/get_users_with_gps/');
            if (isAfterUserLoad) {
                return;
            }

            const isAfterReportLoad = settings.url.includes('geospatial/async/case_management_map/');
            // This indicates clicking Apply button or initial page load
            if (isAfterReportLoad) {
                initUserFilters();
                // Hide controls until data is displayed
                showMapControls(false);
                return;
            }

            // This indicates that report data is fetched either after apply or after pagination
            const isAfterDataLoad = settings.url.includes('geospatial/json/case_management_map/');
            if (!isAfterDataLoad) {
                return;
            }

            showMapControls(true);
            // Hide the datatable rows but not the pagination bar
            $('.dataTables_scroll').hide();

            if (xhr.responseJSON.aaData.length) {
                loadCases(xhr.responseJSON.aaData);
            }

            disbursementRunner = new disbursementRunnerModel();
            $("#disbursement-spinner").koApplyBindings(disbursementRunner);
        });
    });
});
