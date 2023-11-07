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
    const DOWNPLAY_OPACITY = 0.2;
    const HOVER_DELAY = 400;
    const DEFAULT_POLL_TIME_MS = 1500;

    const DEFAULT_CENTER_COORD = [-20.0, -0.0];

    var saveGeoJSONUrl = initialPageData.reverse('geo_polygon');
    var runDisbursementUrl = initialPageData.reverse('case_disbursement');
    var disbursementRunner;
    var caseGroupsIndex = {};

    function getLineFeatureId(itemId) {
        return "route-" + itemId;
    }

    function mapItemModel(itemId, itemData, marker, markerColors) {
        'use strict';
        var self = {};
        self.itemId = itemId;
        self.itemData = itemData;
        self.marker = marker;
        self.selectCssId = "select" + itemId;
        self.isSelected = ko.observable(false);
        self.markerColors = markerColors;

        self.setMarkerOpacity = function (opacity) {
            let element = self.marker.getElement();
            element.style.opacity = opacity;
        };

        function changeMarkerColor(selectedCase, newColor) {
            let marker = selectedCase.marker;
            let element = marker.getElement();
            let svg = element.getElementsByTagName("svg")[0];
            let path = svg.getElementsByTagName("path")[0];
            path.setAttribute("fill", newColor);
        }

        self.getItemType = function () {
            if (self.itemData.type === "user") {
                return gettext("Mobile Worker");
            }
            return gettext("Case");
        };

        self.isSelected.subscribe(function () {
            var color = self.isSelected() ? self.markerColors.selected : self.markerColors.default;
            changeMarkerColor(self, color);
        });
        return self;
    }

    function showMapControls(state) {
        $("#geospatial-map").toggle(state);
        $("#case-buttons").toggle(state);
        $("#mapControls").toggle(state);
        $("#user-filters-panel").toggle(state);
    }

    $(function () {
        // Global var
        var map;

        var caseModels = ko.observableArray([]);
        var userModels = ko.observableArray([]);
        var selectedCases = ko.computed(function () {
            return caseModels().filter(function (currCase) {
                return currCase.isSelected();
            });
        });
        var selectedUsers = ko.computed(function () {
            return userModels().filter(function (currUser) {
                return currUser.isSelected();
            });
        });

        function filterMapItemsInPolygon(polygonFeature) {
            _.values(caseModels()).filter(function (currCase) {
                if (currCase.itemData.coordinates) {
                    currCase.isSelected(isMapItemInPolygon(polygonFeature, currCase.itemData.coordinates));
                }
            });
            _.values(userModels()).filter(function (currUser) {
                if (currUser.itemData.coordinates) {
                    currUser.isSelected(isMapItemInPolygon(polygonFeature, currUser.itemData.coordinates));
                }
            });
        }

        function isMapItemInPolygon(polygonFeature, coordinates) {
            // Will be 0 if a user deletes a point from a three-point polygon,
            // since mapbox will delete the entire polygon. turf.booleanPointInPolygon()
            // does not expect this, and will raise a 'TypeError' exception.
            if (!polygonFeature.geometry.coordinates.length) {
                return false;
            }
            const coordinatesArr = [coordinates.lng, coordinates.lat];
            const point = turf.point(coordinatesArr);  // eslint-disable-line no-undef
            return turf.booleanPointInPolygon(point, polygonFeature.geometry);  // eslint-disable-line no-undef
        }

        var loadMapBox = function (centerCoordinates) {
            'use strict';

            var self = {};
            let clickedMarker;
            mapboxgl.accessToken = initialPageData.get('mapbox_access_token');  // eslint-disable-line no-undef

            if (!centerCoordinates) {
                centerCoordinates = DEFAULT_CENTER_COORD; // should be domain specific
            }

            const map = new mapboxgl.Map({  // eslint-disable-line no-undef
                container: 'geospatial-map', // container ID
                style: 'mapbox://styles/mapbox/streets-v12', // style URL
                center: centerCoordinates, // starting position [lng, lat]
                attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                             ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            });

            const draw = new MapboxDraw({  // eslint-disable-line no-undef
                // API: https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md
                displayControlsDefault: false,
                boxSelect: true, // enables box selection
                controls: {
                    polygon: true,
                    trash: true,
                },
            });

            map.addControl(draw);

            map.on("draw.update", function (e) {
                var selectedFeatures = e.features;

                // Check if any features are selected
                if (!selectedFeatures.length) {
                    return;
                }
                var selectedFeature = selectedFeatures[0];

                if (selectedFeature.geometry.type === 'Polygon') {
                    filterMapItemsInPolygon(selectedFeature);
                }
            });

            map.on('draw.selectionchange', function (e) {
                // See https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md#drawselectionchange
                var selectedFeatures = e.features;
                if (!selectedFeatures.length) {
                    return;
                }

                // Check if any features are selected
                var selectedFeature = selectedFeatures[0];
                // Update this logic if we need to support case filtering by selecting multiple polygons

                if (selectedFeature.geometry.type === 'Polygon') {
                    // Now that we know we selected a polygon, we need to check which markers are inside
                    filterMapItemsInPolygon(selectedFeature);
                }
            });

            function getCoordinates(event) {
                return event.lngLat;
            }

            // We should consider refactoring and splitting the below out to a new JS file
            function moveMarkerToClickedCoordinate(coordinates) {  // eslint-disable-line no-unused-vars
                if (clickedMarker !== null) {
                    clickedMarker.remove();
                }
                if (draw.getMode() === 'draw_polygon') {
                    // It's weird moving the marker around with the ploygon
                    return;
                }
                clickedMarker = new mapboxgl.Marker({color: "FF0000", draggable: true});  // eslint-disable-line no-undef
                clickedMarker.setLngLat(coordinates);
                clickedMarker.addTo(map);
            }

            self.getMapboxDrawInstance = function () {
                return draw;
            };

            self.getMapboxInstance = function () {
                return map;
            };

            self.removeMarkersFromMap = function (itemArr) {
                _.each(itemArr, function (currItem) {
                    currItem.marker.remove();
                });
            };

            self.addMarkersToMap = function (itemArr, markerColours) {
                let outArr = [];
                _.forEach(itemArr, function (item, itemId) {
                    const coordinates = item.coordinates;
                    if (coordinates && coordinates.lat && coordinates.lng) {
                        const mapItem = self.addMarker(itemId, item, markerColours);
                        outArr.push(mapItem);
                    }
                });
                return outArr;
            };

            self.addMarker = function (itemId, itemData, colors) {
                const coordinates = itemData.coordinates;
                // Create the marker
                const marker = new mapboxgl.Marker({ color: colors.default, draggable: false });  // eslint-disable-line no-undef
                marker.setLngLat(coordinates);

                // Add the marker to the map
                marker.addTo(map);

                let popupDiv = document.createElement("div");
                popupDiv.setAttribute("data-bind", "template: 'select-case'");

                let popup = new mapboxgl.Popup({ offset: 25, anchor: "bottom" })  // eslint-disable-line no-undef
                    .setLngLat(coordinates)
                    .setDOMContent(popupDiv);

                marker.setPopup(popup);

                const markerDiv = marker.getElement();
                // Show popup on hover
                markerDiv.addEventListener('mouseenter', () => marker.togglePopup());
                markerDiv.addEventListener('mouseenter', () => highlightMarkerGroup(marker));
                markerDiv.addEventListener('mouseleave', () => resetMarkersOpacity());

                // Hide popup if mouse leaves marker and popup
                var addLeaveEvent = function (fromDiv, toDiv) {
                    fromDiv.addEventListener('mouseleave', function () {
                        setTimeout(function () {
                            if (!$(toDiv).is(':hover')) {
                                // mouse left toDiv as well
                                marker.togglePopup();
                            }
                        }, 100);
                    });
                };
                addLeaveEvent(markerDiv, popupDiv);
                addLeaveEvent(popupDiv, markerDiv);

                const mapItemInstance = new mapItemModel(itemId, itemData, marker, colors);
                $(popupDiv).koApplyBindings(mapItemInstance);

                return mapItemInstance;
            };

            ko.applyBindings({'userModels': userModels, 'selectedUsers': selectedUsers}, $("#user-modals")[0]);
            ko.applyBindings({'caseModels': caseModels, 'selectedCases': selectedCases}, $("#case-modals")[0]);
            // Handle click events here
            map.on('click', (event) => {
                let coordinates = getCoordinates(event);  // eslint-disable-line no-unused-vars
            });
            return self;
        };

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

        function resetMarkersOpacity() {
            let mapInstance = map.getMapboxInstance();
            let markers = [];
            Object.keys(caseGroupsIndex).forEach(itemCoordinates => {
                const mapMarkerItem = caseGroupsIndex[itemCoordinates];
                markers.push(mapMarkerItem.item);

                const lineId = getLineFeatureId(mapMarkerItem.item.itemId);
                if (mapInstance.getLayer(lineId)) {
                    mapInstance.setPaintProperty(lineId, 'line-opacity', 1);
                }
            });
            changeMarkersOpacity(markers, 1);
        }

        function highlightMarkerGroup(marker) {
            const markerCoords = marker.getLngLat();
            const currentMarkerPosition = markerCoords.lng + " " + markerCoords.lat;
            const markerItem = caseGroupsIndex[currentMarkerPosition];
            let mapInstance = map.getMapboxInstance();

            if (markerItem) {
                const groupId = markerItem.groupId;

                let markersToHide = [];
                Object.keys(caseGroupsIndex).forEach(itemCoordinates => {
                    const mapMarkerItem = caseGroupsIndex[itemCoordinates];

                    if (mapMarkerItem.groupId !== groupId) {
                        markersToHide.push(mapMarkerItem.item);
                        const lineId = getLineFeatureId(mapMarkerItem.item.itemId);
                        if (mapInstance.getLayer(lineId)) {
                            mapInstance.setPaintProperty(lineId, 'line-opacity', DOWNPLAY_OPACITY);
                        }
                    }
                });
                changeMarkersOpacity(markersToHide, DOWNPLAY_OPACITY);
            }
        }

        function changeMarkersOpacity(markers, opacity) {
            // It's necessary to delay obscuring the markers since mapbox does not play nice
            // if we try to do it all at once.
            setTimeout(function () {
                markers.forEach(marker => {
                    marker.setMarkerOpacity(opacity);
                });
            }, HOVER_DELAY);
        }

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

        function savedPolygon(polygon) {
            var self = {};
            self.text = polygon.name;
            self.id = polygon.id;
            self.geoJson = polygon.geo_json;
            return self;
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

        var mapControlsModel = function () {
            'use strict';
            var self = {};
            var mapboxinstance = map.getMapboxInstance();
            self.btnRunDisbursementDisabled = ko.computed(function () {
                return !caseModels().length || !userModels().length;
            });
            self.btnSaveDisabled = ko.observable(true);
            self.btnExportDisabled = ko.observable(true);

            // initial saved polygons
            self.savedPolygons = ko.observableArray();
            _.each(initialPageData.get('saved_polygons'), function (polygon) {
                self.savedPolygons.push(savedPolygon(polygon));
            });
            // Keep track of the Polygon selected by the user
            self.selectedPolygon = ko.observable();
            // Keep track of the Polygon displayed
            self.activePolygon = ko.observable();

            // On selection, add the polygon to the map
            self.selectedPolygon.subscribe(function (value) {
                const polygonId = parseInt(self.selectedPolygon());
                var polygonObj = self.savedPolygons().find(
                    function (o) { return o.id === polygonId; }
                );
                if (!polygonObj) {
                    return;
                }

                // Clear existing polygon
                if (self.activePolygon()) {
                    mapboxinstance.removeLayer(self.activePolygon());
                    mapboxinstance.removeSource(self.activePolygon());
                }
                if (value !== undefined) {
                    // Add selected polygon
                    mapboxinstance.addSource(
                        String(polygonObj.id),
                        {'type': 'geojson', 'data': polygonObj.geoJson}
                    );
                    mapboxinstance.addLayer({
                        'id': String(polygonObj.id),
                        'type': 'fill',
                        'source': String(polygonObj.id),
                        'layout': {},
                        'paint': {
                            'fill-color': '#0080ff',
                            'fill-opacity': 0.5,
                        },
                    });
                    polygonObj.geoJson.features.forEach(
                        filterMapItemsInPolygon
                    );
                    self.btnExportDisabled(false);
                    self.btnSaveDisabled(true);
                }
                // Mark as active polygon
                self.activePolygon(self.selectedPolygon());
            });

            var mapHasPolygons = function () {
                var drawnFeatures = map.getMapboxDrawInstance().getAll().features;
                if (!drawnFeatures.length) {
                    return false;
                }
                return drawnFeatures.some(function (feature) {
                    return feature.geometry.type === "Polygon";
                });
            };

            mapboxinstance.on('draw.delete', function () {
                self.btnSaveDisabled(!mapHasPolygons());
            });

            mapboxinstance.on('draw.create', function () {
                self.btnSaveDisabled(!mapHasPolygons());
            });

            self.exportGeoJson = function () {
                var exportButton = $("#btnExportDrawnArea");
                var selectedPolygon = self.savedPolygons().find(
                    function (o) { return o.id === self.selectedPolygon(); }
                );
                if (selectedPolygon) {
                    var convertedData = 'text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(selectedPolygon.geoJson));
                    exportButton.attr('href', 'data:' + convertedData);
                    exportButton.attr('download','data.geojson');
                }
            };

            return self;
        };

        function initMapControls() {
            // Assumes `map` var is initialized
            var $mapControlDiv = $("#mapControls");
            var mapControlsModelInstance = mapControlsModel();
            if ($mapControlDiv.length) {
                ko.cleanNode($mapControlDiv[0]);
                $mapControlDiv.koApplyBindings(mapControlsModelInstance);
            }

            var $saveDrawnArea = $("#btnSaveDrawnArea");
            $saveDrawnArea.click(function () {
                if (map) {
                    saveGeoJson(map.getMapboxDrawInstance(), mapControlsModelInstance);
                }
            });

            var $exportDrawnArea = $("#btnExportDrawnArea");
            $exportDrawnArea.click(function () {
                if (map) {
                    mapControlsModelInstance.exportGeoJson();
                }
            });

            var $runDisbursement = $("#btnRunDisbursement");
            $runDisbursement.click(function () {
                if (map) {
                    disbursementRunner.runCaseDisbursementAlgorithm(caseModels(), userModels());
                }
            });
        }

        var missingGPSModel = function () {
            this.casesWithoutGPS = ko.observable([]);
            this.usersWithoutGPS = ko.observable([]);
        };
        var missingGPSModelInstance = new missingGPSModel();

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

        // @param mapItems - Should be an array of mapItemModel type objects
        function fitMapBounds(mapItems) {
            const mapInstance = map.getMapboxInstance();
            if (!mapItems.length) {
                mapInstance.flyTo({
                    zoom: 0,
                    center: DEFAULT_CENTER_COORD,
                    duration: 500,
                });
                return;
            }

            // See https://stackoverflow.com/questions/62939325/scale-mapbox-gl-map-to-fit-set-of-markers
            const firstCoord = mapItems[0].itemData.coordinates;
            const bounds = mapItems.reduce(function (bounds, mapItem) {
                const coord = mapItem.itemData.coordinates;
                if (coord) {
                    return bounds.extend(coord);
                }
            }, new mapboxgl.LngLatBounds(firstCoord, firstCoord));  // eslint-disable-line no-undef

            map.getMapboxInstance().fitBounds(bounds, {
                padding: 50,  // in pixels
                duration: 500,  // in ms
                maxZoom: 10,  // 0-23
            });
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
                map = loadMapBox();
                initMapControls();
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

            if (xhr.responseJSON.aaData.length && map) {
                loadCases(xhr.responseJSON.aaData);
            }

            disbursementRunner = new disbursementRunnerModel();
            $("#disbursement-spinner").koApplyBindings(disbursementRunner);
        });
    });
});
