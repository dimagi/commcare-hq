hqDefine("geospatial/js/geospatial_map", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "knockout",
    'geospatial/js/models',
    'select2/dist/js/select2.full.min',
], function (
    $,
    initialPageData,
    ko,
    models
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

    const MAP_CONTAINER_ID = 'geospatial-map';

    var saveGeoJSONUrl = initialPageData.reverse('geo_polygon');
    var runDisbursementUrl = initialPageData.reverse('case_disbursement');
    var disbursementRunner;

    var mapModel;
    var polygonFilterModel;
    var missingGPSModelInstance;

    function showMapControls(state) {
        $("#geospatial-map").toggle(state);
        $("#case-buttons").toggle(state);
        $("#mapControls").toggle(state);
        $("#user-filters-panel").toggle(state);
    }

    var saveGeoJson = function () {
        const data = mapModel.drawControls.getAll();
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
                    mapModel.drawControls.deleteAll();
                    console.log('newPoly', name);
                    polygonFilterModel.savedPolygons.push(
                        new models.SavedPolygon({
                            name: name,
                            id: ret.id,
                            geo_json: data,
                        })
                    );
                    // redraw using mapControlsModelInstance
                    polygonFilterModel.selectedSavedPolygonId(ret.id);
                },
            });
        }
    };

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
                let user = mapModel.userMapItems().find((userModel) => {return userModel.itemId === userId;});
                const userCoordString = user.itemData.coordinates['lng'] + " " + user.itemData.coordinates['lat'];
                mapModel.caseGroupsIndex[userCoordString] = {groupId: groupId, item: user};

                let cases = [];
                mapModel.caseMapItems().forEach((caseModel) => {
                    if (result[userId].includes(caseModel.itemId)) {
                        cases.push(caseModel);
                        const coordString = caseModel.itemData.coordinates['lng'] + " " + caseModel.itemData.coordinates['lat'];
                        mapModel.caseGroupsIndex[coordString] = {groupId: groupId, item: caseModel};
                    }
                });
                connectUserWithCasesOnMap(user, cases);
                groupId += 1;
            });
            self.setBusy(false);
        };

        self.runCaseDisbursementAlgorithm = function (cases, users) {
            self.setBusy(true);
            let mapInstance = mapModel.mapInstance;

            let caseData = [];
            cases.forEach(function (c) {
                const layerId = mapModel.getLineFeatureId(c.itemId);
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

        function connectUserWithCasesOnMap(user, cases) {
            cases.forEach((caseModel) => {
                const lineCoordinates = [
                    [user.itemData.coordinates.lng, user.itemData.coordinates.lat],
                    [caseModel.itemData.coordinates.lng, caseModel.itemData.coordinates.lat],
                ];
                let mapInstance = mapModel.mapInstance;
                mapInstance.addLayer({
                    id: mapModel.getLineFeatureId(caseModel.itemId),
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

        return self;
    };

    function initMap() {
        mapModel = new models.Map();
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

        mapModel.mapInstance.on("draw.update", (e) => {
            mapModel.selectAllMapItems(e.features);
        });
        mapModel.mapInstance.on('draw.selectionchange', (e) => {
            mapModel.selectAllMapItems(e.features);
        });
        mapModel.mapInstance.on('draw.delete', function () {
            // TODO: Need to fix this
            polygonFilterModel.btnSaveDisabled(!mapModel.mapHasPolygons());
        });
        mapModel.mapInstance.on('draw.create', function () {
            // TODO: Need to fix this
            polygonFilterModel.btnSaveDisabled(!mapModel.mapHasPolygons());
        });
        loadMapBoxStreetsLayers(mapModel.mapInstance);
    }

    function loadMapBoxStreetsLayers(map) {
        map.on('load', () => {
            map.addSource('mapbox-streets', {
                type: 'vector',
                url: 'mapbox://mapbox.mapbox-streets-v8'
            });
            // templates: line
//            map.addLayer({
//                id: '',
//                source: 'mapbox-streets',
//                'source-layer': '',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
             // templates: circle
//            map.addLayer({
//                id: '',
//                source: 'mapbox-streets',
//                'source-layer': '',
//                "type": "circle",
//                "paint": {
//                    "circle-radius": 3,
//                    "circle-color": "rgba(238,78,139, 0.4)",
//                    "circle-stroke-color": "rgba(238,78,139, 1)",
//                    "circle-stroke-width": 1
//                }
//            });
            // templates: fill
//              map.addLayer({
//                id: '',
//                source: 'mapbox-streets',
//                'source-layer': '',
//                type: 'fill',
//                "paint": {
//                    "fill-color": "rgba(66,100,251, 0.3)",
//                    "fill-outline-color": "rgba(66,100,251, 1)"
//                }
//              });
            // landuse; minzoom 5 [No changes to map]
//            map.addLayer({
//                id: 'landuse',
//                source: 'mapbox-streets',
//                'source-layer': 'landuse',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
            // waterway; minzoom: 7 [No changes to map; possibly already present]
//            map.addLayer({
//                id: 'waterway',
//                source: 'mapbox-streets',
//                'source-layer': 'waterway',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
            // water; minzoom: 0 [No changes to map; possibly already present]
//            map.addLayer({
//                id: 'water',
//                source: 'mapbox-streets',
//                'source-layer': 'water',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
            // aeroway; mizoom: 9 [No changes to map]
//            map.addLayer({
//                id: 'aeroway',
//                source: 'mapbox-streets',
//                'source-layer': 'aeroway',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
              // structure; minzoom: 13 [No changes to map]
//            map.addLayer({
//                id: 'structure',
//                source: 'mapbox-streets',
//                'source-layer': 'structure',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
            // building; minzoom: 12 [No changes to map]
//            map.addLayer({
//                id: 'mapbox-building',
//                source: 'mapbox-streets',
//                'source-layer': 'building',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
            // landuse_overlay; minzoom: 5 [Works]
//            map.addLayer({
//                id: 'landuse_overlay',
//                source: 'mapbox-streets',
//                'source-layer': 'landuse_overlay',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
              // road; minzoom: 3 [Works]
//            map.addLayer({
//                id: 'road',
//                source: 'mapbox-streets',
//                'source-layer': 'road',
//                type: 'line',
//                paint: {
//                    'line-color': '#023020' // dark green
//                }
//            });
            // admin; minzoom: 0 [Works]
//            map.addLayer({
//                id: 'admin',
//                source: 'mapbox-streets',
//                'source-layer': 'admin',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
            // place_label; minzoom: 0 [No changes to map; possibly already present]
//            map.addLayer({
//                id: 'place_label',
//                source: 'mapbox-streets',
//                'source-layer': 'place_label',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
            // airport_label; minzoom: 8 [No changes to map; possibly already present]
//            map.addLayer({
//                id: 'airport_label',
//                source: 'mapbox-streets',
//                'source-layer': 'airport_label',
//                type: 'line',
//                paint: {
//                    'line-color': '#800080' // purple
//                }
//            });
            // transit_stop_label; minzoom: 5 [No changes to map]
//            map.addLayer({
//                id: 'transit_stop_label',
//                source: 'mapbox-streets',
//                'source-layer': 'transit_stop_label',
//                "type": "circle",
//                "paint": {
//                    "circle-radius": 3,
//                    "circle-color": "rgba(238,78,139, 0.4)",
//                    "circle-stroke-color": "rgba(238,78,139, 1)",
//                    "circle-stroke-width": 1
//                }
//            });
        });
    }

    function initPolygonFilters() {
        // Assumes `map` var is initialized
        const $mapControlDiv = $("#mapControls");
        polygonFilterModel = new models.PolygonFilter(mapModel, false, true);
        polygonFilterModel.loadPolygons(initialPageData.get('saved_polygons'));
        if ($mapControlDiv.length) {
            ko.cleanNode($mapControlDiv[0]);
            $mapControlDiv.koApplyBindings(polygonFilterModel);
        }

        const $saveDrawnArea = $("#btnSaveDrawnArea");
        $saveDrawnArea.click(function () {
            if (mapModel && mapModel.mapInstance) {
                saveGeoJson();
            }
        });

        var $exportDrawnArea = $("#btnExportDrawnArea");
        $exportDrawnArea.click(function () {
            if (mapModel && mapModel.mapInstance) {
                polygonFilterModel.exportGeoJson("btnExportDrawnArea");
            }
        });

        var $runDisbursement = $("#btnRunDisbursement");
        $runDisbursement.click(function () {
            if (mapModel && mapModel.mapInstance) {
                disbursementRunner.runCaseDisbursementAlgorithm(mapModel.caseMapItems(), mapModel.userMapItems());
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

        self.loadUsers = function () {
            mapModel.removeMarkersFromMap(mapModel.userMapItems());
            mapModel.userMapItems([]);
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

                    const userMapItems = mapModel.addMarkersToMap(userData, userMarkerColors);
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
        mapModel.removeMarkersFromMap(mapModel.caseMapItems());
        mapModel.caseMapItems([]);
        var casesWithGPS = caseData.filter(function (item) {
            return item[1] !== null;
        });
        // Index by case_id
        var casesById = _.object(_.map(casesWithGPS, function (item) {
            if (item[1]) {
                return [item[0], {'coordinates': item[1], 'link': item[2], 'type': 'case'}];
            }
        }));
        const caseMapItems = mapModel.addMarkersToMap(casesById, caseMarkerColors);
        mapModel.caseMapItems(caseMapItems);

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

        mapModel.fitMapBounds(caseMapItems);
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
            initMap();
            initPolygonFilters();
            initUserFilters();
            // Hide controls until data is displayed
            showMapControls(false);
            missingGPSModelInstance = new models.MissingGPSModel();

            disbursementRunner = new disbursementRunnerModel();
            $("#disbursement-spinner").koApplyBindings(disbursementRunner);

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

        if (xhr.responseJSON.aaData.length && mapModel.mapInstance) {
            loadCases(xhr.responseJSON.aaData);
        }
    });
});
