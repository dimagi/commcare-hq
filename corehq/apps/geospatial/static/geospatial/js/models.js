hqDefine('geospatial/js/models', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'geospatial/js/utils',
], function (
    $,
    ko,
    initialPageData,
    utils
) {
    const HOVER_DELAY = 400;
    const DOWNPLAY_OPACITY = 0.2;
    const FEATURE_QUERY_PARAM = 'features';
    const DEFAULT_CENTER_COORD = [-20.0, -0.0];

    var MissingGPSModel = function () {
        this.casesWithoutGPS = ko.observable([]);
        this.usersWithoutGPS = ko.observable([]);
    };

    var SavedPolygon = function (polygon) {
        var self = this;
        self.text = polygon.name;
        self.id = polygon.id;
        self.geoJson = polygon.geo_json;
    };

    var MapItem = function (itemId, itemData, marker, markerColors) {
        'use strict';
        var self = this;
        self.itemId = itemId;
        self.itemData = itemData;
        self.marker = marker;
        self.selectCssId = "select" + itemId;
        self.isSelected = ko.observable(false);
        self.markerColors = markerColors;

        self.groupId = null;
        self.groupCoordinates = null;

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
    };

    var GroupedCaseMapItem = function (itemId, itemData, link) {
        let self = this;
        self.itemId = itemId;
        self.itemData = itemData;
        self.link = link;
        self.groupId = null;
        self.groupCoordinates = null;

        self.toJson = function () {
            const coordinates = (self.itemData.coordinates) ? `${self.itemData.coordinates.lng} ${self.itemData.coordinates.lat}` : "";
            const groupCoordinates = (self.groupCoordinates) ? `${self.groupCoordinates.lng} ${self.groupCoordinates.lat}` : "";
            return {
                'groupId': self.groupId,
                'groupCenterCoordinates': groupCoordinates,
                'caseId': self.itemId,
                'coordinates': coordinates,
            };
        };
    };

    var Map = function (usesClusters) {
        var self = this;

        self.usesClusters = usesClusters;

        self.mapInstance;
        self.drawControls;

        self.caseMapItems = ko.observableArray([]);
        self.userMapItems = ko.observableArray([]);

        self.caseGroupsIndex = {};

        self.initMap = function (mapDivId, centerCoordinates) {
            mapboxgl.accessToken = initialPageData.get('mapbox_access_token');  // eslint-disable-line no-undef
            if (!centerCoordinates) {
                centerCoordinates = [-91.874, 42.76]; // should be domain specific
            }

            self.mapInstance = new mapboxgl.Map({  // eslint-disable-line no-undef
                container: mapDivId, // container ID
                style: 'mapbox://styles/mapbox/streets-v12', // style URL
                center: centerCoordinates, // starting position [lng, lat]
                zoom: 12,
                attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                             ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            });

            self.drawControls = new MapboxDraw({  // eslint-disable-line no-undef
                // API: https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md
                displayControlsDefault: false,
                boxSelect: true, // enables box selection
                controls: {
                    polygon: true,
                    trash: true,
                },
            });
            self.mapInstance.addControl(self.drawControls);
            if (self.usesClusters) {
                createClusterLayers();
            }
        };

        function createClusterLayers() {
            // const mapInstance = self.mapInstance;
            self.mapInstance.on('load', () => {
                self.mapInstance.addSource('caseWithGPS', {
                    type: 'geojson',
                    data: {
                        "type": "FeatureCollection",
                        "features": [],
                    },
                    cluster: true,
                    clusterMaxZoom: 14, // Max zoom to cluster points on
                    clusterRadius: 50, // Radius of each cluster when clustering points (defaults to 50)
                });
                self.mapInstance.addLayer({
                    id: 'clusters',
                    type: 'circle',
                    source: 'caseWithGPS',
                    filter: ['has', 'point_count'],
                    paint: {
                        'circle-color': [
                            'step',
                            ['get', 'point_count'],
                            '#51bbd6',
                            100,
                            '#f1f075',
                            750,
                            '#f28cb1',
                        ],
                        'circle-radius': [
                            'step',
                            ['get', 'point_count'],
                            20,
                            100,
                            30,
                            750,
                            40,
                        ],
                    },
                });
                self.mapInstance.addLayer({
                    id: 'cluster-count',
                    type: 'symbol',
                    source: 'caseWithGPS',
                    filter: ['has', 'point_count'],
                    layout: {
                        'text-field': ['get', 'point_count_abbreviated'],
                        'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Bold'],
                        'text-size': 12,
                    },
                });
                self.mapInstance.addLayer({
                    id: 'unclustered-point',
                    type: 'circle',
                    source: 'caseWithGPS',
                    filter: ['!', ['has', 'point_count']],
                    paint: {
                        'circle-color': 'red',
                        'circle-radius': 10,
                        'circle-stroke-width': 1,
                        'circle-stroke-color': '#fff',
                    },
                });
            });
        }

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
                    const mapItem = addMarker(itemId, item, markerColours);
                    outArr.push(mapItem);
                }
            });
            return outArr;
        };

        function addMarker(itemId, itemData, colors) {
            const coordinates = itemData.coordinates;
            // Create the marker
            const marker = new mapboxgl.Marker({ color: colors.default, draggable: false });  // eslint-disable-line no-undef
            marker.setLngLat(coordinates);

            // Add the marker to the map
            marker.addTo(self.mapInstance);

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

            const mapItemInstance = new MapItem(itemId, itemData, marker, colors);
            $(popupDiv).koApplyBindings(mapItemInstance);

            return mapItemInstance;
        }

        function resetMarkersOpacity() {
            let markers = [];
            Object.keys(self.caseGroupsIndex).forEach(itemCoordinates => {
                const mapMarkerItem = self.caseGroupsIndex[itemCoordinates];
                markers.push(mapMarkerItem.item);

                const lineId = self.getLineFeatureId(mapMarkerItem.item.itemId);
                if (self.mapInstance.getLayer(lineId)) {
                    self.mapInstance.setPaintProperty(lineId, 'line-opacity', 1);
                }
            });
            changeMarkersOpacity(markers, 1);
        }

        function highlightMarkerGroup(marker) {
            const markerCoords = marker.getLngLat();
            const currentMarkerPosition = markerCoords.lng + " " + markerCoords.lat;
            const markerItem = self.caseGroupsIndex[currentMarkerPosition];

            if (markerItem) {
                const groupId = markerItem.groupId;

                let markersToHide = [];
                Object.keys(self.caseGroupsIndex).forEach(itemCoordinates => {
                    const mapMarkerItem = self.caseGroupsIndex[itemCoordinates];

                    if (mapMarkerItem.groupId !== groupId) {
                        markersToHide.push(mapMarkerItem.item);
                        const lineId = self.getLineFeatureId(mapMarkerItem.item.itemId);
                        if (self.mapInstance.getLayer(lineId)) {
                            self.mapInstance.setPaintProperty(lineId, 'line-opacity', DOWNPLAY_OPACITY);
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

        self.getLineFeatureId = function (itemId) {
            return "route-" + itemId;
        };

        self.selectAllMapItems = function (featuresArr) {
            // See https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md#drawselectionchange
            if (!featuresArr.length) {
                return;
            }

            for (const feature of featuresArr) {
                if (feature.geometry.type === 'Polygon') {
                    self.selectMapItemsInPolygon(feature, self.caseMapItems());
                    self.selectMapItemsInPolygon(feature, self.userMapItems());
                }
            }
        };

        self.selectMapItemsInPolygon = function (polygonFeature, mapItems) {
            _.values(mapItems).filter(function (mapItem) {
                if (mapItem.itemData.coordinates) {
                    mapItem.isSelected(isMapItemInPolygon(polygonFeature, mapItem.itemData.coordinates));
                }
            });
        };

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

        self.mapHasPolygons = function () {
            const drawnFeatures = self.drawControls.getAll().features;
            if (!drawnFeatures.length) {
                return false;
            }
            return drawnFeatures.some(function (feature) {
                return feature.geometry.type === "Polygon";
            });
        };

        // @param mapItems - Should be an array of mapItemModel type objects
        self.fitMapBounds = function (mapItems) {
            if (!mapItems.length) {
                self.mapInstance.flyTo({
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

            self.mapInstance.fitBounds(bounds, {
                padding: 50,  // in pixels
                duration: 500,  // in ms
                maxZoom: 10,  // 0-23
            });
        };
    };

    var PolygonFilter = function (mapObj, shouldUpdateQueryParam, shouldSelectAfterFilter) {
        var self = this;

        self.mapObj = mapObj;

        // TODO: This can be moved to geospatial JS (specific functionality)
        self.btnRunDisbursementDisabled = ko.computed(function () {
            return !self.mapObj.caseMapItems().length || !self.mapObj.userMapItems().length;
        });

        self.shouldUpdateQuryParam = shouldUpdateQueryParam;
        self.shouldSelectAfterFilter = shouldSelectAfterFilter;
        self.btnSaveDisabled = ko.observable(true);
        self.btnExportDisabled = ko.observable(true);

        self.polygons = {};
        self.shouldRefreshPage = ko.observable(false);

        self.savedPolygons = ko.observableArray([]);
        self.selectedSavedPolygonId = ko.observable('');
        self.activeSavedPolygon;

        self.addPolygonsToFilterList = function (featureList) {
            for (const feature of featureList) {
                self.polygons[feature.id] = feature;
            }
            if (self.shouldUpdateQuryParam) {
                updatePolygonQueryParam();
            }
        };

        self.removePolygonsFromFilterList = function (featureList) {
            for (const feature of featureList) {
                if (self.polygons[feature.id]) {
                    delete self.polygons[feature.id];
                }
            }
            if (self.shouldUpdateQuryParam) {
                updatePolygonQueryParam();
            }
        };

        function updatePolygonQueryParam() {
            const url = new URL(window.location.href);
            if (Object.keys(self.polygons).length) {
                url.searchParams.set(FEATURE_QUERY_PARAM, JSON.stringify(self.polygons));
            } else {
                url.searchParams.delete(FEATURE_QUERY_PARAM);
            }
            window.history.replaceState({ path: url.href }, '', url.href);
            self.shouldRefreshPage(true);
        }

        self.loadPolygonFromQueryParam = function () {
            const url = new URL(window.location.href);
            const featureParam = url.searchParams.get(FEATURE_QUERY_PARAM);
            if (featureParam) {
                const features = JSON.parse(featureParam);
                for (const featureId in features) {
                    const feature = features[featureId];
                    self.mapObj.drawControls.add(feature);
                    self.polygons[featureId] = feature;
                }
            }
        };

        function removeActivePolygonLayer() {
            if (self.activeSavedPolygon) {
                self.mapObj.mapInstance.removeLayer(self.activeSavedPolygon.id);
                self.mapObj.mapInstance.removeSource(self.activeSavedPolygon.id);
            }
        }

        function createActivePolygonLayer(polygonObj) {
            self.mapObj.mapInstance.addSource(
                String(polygonObj.id),
                {'type': 'geojson', 'data': polygonObj.geoJson}
            );
            self.mapObj.mapInstance.addLayer({
                'id': String(polygonObj.id),
                'type': 'fill',
                'source': String(polygonObj.id),
                'layout': {},
                'paint': {
                    'fill-color': '#0080ff',
                    'fill-opacity': 0.5,
                },
            });
        }

        self.clearActivePolygon = function () {
            if (self.activeSavedPolygon) {
                // self.selectedSavedPolygonId('');
                self.removePolygonsFromFilterList(self.activeSavedPolygon.geoJson.features);
                removeActivePolygonLayer();
                self.activeSavedPolygon = null;
                self.btnSaveDisabled(false);
                self.btnExportDisabled(true);
            }
        };

        self.selectedSavedPolygonId.subscribe(() => {
            const selectedId = parseInt(self.selectedSavedPolygonId());
            const polygonObj = self.savedPolygons().find(
                function (o) { return o.id === selectedId; }
            );
            if (!polygonObj) {
                return;
            }

            self.clearActivePolygon();

            removeActivePolygonLayer();
            createActivePolygonLayer(polygonObj);

            self.activeSavedPolygon = polygonObj;
            self.addPolygonsToFilterList(polygonObj.geoJson.features);
            self.btnExportDisabled(false);
            self.btnSaveDisabled(true);
            if (self.shouldSelectAfterFilter) {
                self.mapObj.selectAllMapItems(polygonObj.geoJson.features);
            }
        });

        self.loadPolygons = function (polygonArr) {
            if (self.shouldUpdateQuryParam) {
                self.loadPolygonFromQueryParam();
            }
            self.savedPolygons([]);

            _.each(polygonArr, (polygon) => {
                // Saved features don't have IDs, so we need to give them to uniquely identify them for polygon filtering
                for (const feature of polygon.geo_json.features) {
                    feature.id = utils.uuidv4();
                }
                self.savedPolygons.push(new SavedPolygon(polygon));
            });
        };

        self.exportGeoJson = function (exportButtonId) {
            const exportButton = $(`#${exportButtonId}`);
            const selectedId = parseInt(self.selectedSavedPolygonId());
            const selectedPolygon = self.savedPolygons().find(
                function (o) { return o.id === selectedId; }
            );
            if (selectedPolygon) {
                const convertedData = 'text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(selectedPolygon.geoJson));
                exportButton.attr('href', 'data:' + convertedData);
                exportButton.attr('download','data.geojson');
            }
        };
    };

    return {
        MissingGPSModel: MissingGPSModel,
        SavedPolygon: SavedPolygon,
        MapItem: MapItem,
        GroupedCaseMapItem: GroupedCaseMapItem,
        Map: Map,
        PolygonFilter: PolygonFilter,
    };
});