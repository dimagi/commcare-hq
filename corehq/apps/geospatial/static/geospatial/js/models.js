'use strict';
hqDefine('geospatial/js/models', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'geospatial/js/utils',
], function (
    $,
    ko,
    _,
    initialPageData,
    utils
) {
    const DOWNPLAY_OPACITY = 0.2;
    const FEATURE_QUERY_PARAM = 'features';
    const DEFAULT_CENTER_COORD = [-20.0, -0.0];
    const DISBURSEMENT_LAYER_PREFIX = 'route-';

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
            const element = self.marker.getElement();
            const svg = element.getElementsByTagName("svg")[0];
            svg.setAttribute("opacity", opacity);
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
                'caseName': self.itemData.case_name,
                'owner_id': self.itemData.owner_id,
                'owner_name': self.itemData.owner_name,
                'coordinates': coordinates,
            };
        };
    };

    var Map = function (usesClusters, usesStreetsLayers) {
        var self = this;

        self.usesClusters = usesClusters;
        self.usesStreetsLayers = usesStreetsLayers;

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

            if (self.usesStreetsLayers) {
                loadMapBoxStreetsLayers();
                addLayersToPanel();
            }
        };

        function loadMapBoxStreetsLayers() {
            self.mapInstance.on('load', () => {
                self.mapInstance.addSource('mapbox-streets', {
                    type: 'vector',
                    url: 'mapbox://mapbox.mapbox-streets-v8',
                });

                self.mapInstance.addLayer({
                    id: 'Landuse',
                    source: 'mapbox-streets',
                    'source-layer': 'landuse',
                    type: 'line',
                    paint: {
                        'line-color': '#695447', // brown land color
                    },
                    layout: {
                        'visibility': 'none',
                    },
                });
                self.mapInstance.addLayer({
                    id: 'Road',
                    source: 'mapbox-streets',
                    'source-layer': 'road',
                    type: 'line',
                    paint: {
                        'line-color': '#000000', // black
                    },
                    layout: {
                        'visibility': 'none',
                    },
                });
                self.mapInstance.addLayer({
                    id: 'Admin',
                    source: 'mapbox-streets',
                    'source-layer': 'admin',
                    type: 'line',
                    paint: {
                        'line-color': '#800080', // purple
                    },
                    layout: {
                        'visibility': 'none',
                    },
                });
                self.mapInstance.addLayer({
                    id: 'Building',
                    source: 'mapbox-streets',
                    'source-layer': 'building',
                    type: 'fill',
                    paint: {
                        'fill-color': '#808080', // grey
                    },
                    layout: {
                        'visibility': 'none',
                    },
                });
                self.mapInstance.addLayer({
                    id: 'Waterway',
                    source: 'mapbox-streets',
                    'source-layer': 'waterway',
                    type: 'line',
                    paint: {
                        'line-color': '#00008b', // darkblue
                    },
                    layout: {
                        'visibility': 'none',
                    },
                });
                self.mapInstance.addLayer({
                    id: 'Building',
                    source: 'mapbox-streets',
                    'source-layer': 'building',
                    type: 'fill',
                    paint: {
                        'fill-color': '#808080', // grey
                    },
                    'layout': {
                        'visibility': 'none',
                    },
                });

                self.mapInstance.addLayer({
                    id: 'Landuse',
                    source: 'mapbox-streets',
                    'source-layer': 'landuse',
                    type: 'line',
                    paint: {
                        'line-color': '#695447', // brown land color
                    },
                    'layout': {
                        'visibility': 'none',
                    },
                });

                self.mapInstance.addLayer({
                    id: 'Road',
                    source: 'mapbox-streets',
                    'source-layer': 'road',
                    type: 'line',
                    paint: {
                        'line-color': '#000000', // black
                    },
                    'layout': {
                        'visibility': 'none',
                    },
                });

                self.mapInstance.addLayer({
                    id: 'Waterway',
                    source: 'mapbox-streets',
                    'source-layer': 'waterway',
                    type: 'line',
                    paint: {
                        'line-color': '#00008b', // darkblue
                    },
                    'layout': {
                        'visibility': 'none',
                    },
                });

            });
        }

        function addLayersToPanel() {
            self.mapInstance.on('idle', () => {
                const toggleableLayerIds = [
                    'Landuse',
                    'Admin',
                    'Road',
                    'Building',
                    'Waterway',
                ];
                const menuElement = document.getElementById('layer-toggle-menu');
                for (const layerId of toggleableLayerIds) {
                    // Skip if layer doesn't exist or button is already present
                    if (!self.mapInstance.getLayer(layerId) || document.getElementById(layerId)) {
                        continue;
                    }

                    const link = document.createElement('a');
                    link.id = layerId;
                    link.role = 'button';
                    link.href = '#';
                    link.textContent = layerId;
                    link.className = 'btn btn-secondary';
                    link.onclick = function (e) {
                        const clickedLayer = this.textContent;
                        e.preventDefault();
                        e.stopPropagation();

                        const visibility = self.mapInstance.getLayoutProperty(clickedLayer, 'visibility');
                        if (visibility === 'visible') {
                            self.mapInstance.setLayoutProperty(clickedLayer, 'visibility', 'none');
                            this.classList.remove('active');
                        } else {
                            this.classList.add('active');
                            self.mapInstance.setLayoutProperty(clickedLayer, 'visibility', 'visible');
                        }
                    };

                    menuElement.appendChild(link);
                }
                menuElement.classList.remove('hidden');
            });
        }

        function createClusterLayers() {
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

            const popupDiv = document.createElement("div");
            const popup = utils.createMapPopup(
                coordinates,
                popupDiv,
                () => highlightMarkerGroup(itemId),
                resetMarkersOpacity
            );

            marker.setPopup(popup);
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

        function highlightMarkerGroup(itemId) {
            const markerItem = self.caseGroupsIndex[itemId];
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
            markers.forEach(marker => {
                marker.setMarkerOpacity(opacity);
            });
        }

        self.getLineFeatureId = function (itemId) {
            return DISBURSEMENT_LAYER_PREFIX + itemId;
        };

        self.selectAllMapItems = function (featuresArr) {
            // See https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md#drawselectionchange
            for (const caseItem of self.caseMapItems()) {
                self.selectMapItemInPolygons(featuresArr, caseItem);
            }
            for (const userItem of self.userMapItems()) {
                self.selectMapItemInPolygons(featuresArr, userItem);
            }
        };

        self.selectMapItemInPolygons = function (polygonArr, mapItem) {
            let isSelected = false;
            for (const polygon of polygonArr) {
                if (polygon.geometry.type !== 'Polygon') {
                    continue;
                }
                if (isMapItemInPolygon(polygon, mapItem.itemData.coordinates)) {
                    isSelected = true;
                    break;
                }
            }
            mapItem.isSelected(isSelected);
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

        self.hasDisbursementLayers = function () {
            const mapLayers = self.mapInstance.getStyle().layers;
            return _.any(
                mapLayers,
                function (layer) { return layer.id.includes(DISBURSEMENT_LAYER_PREFIX); }
            );
        };

        self.removeDisbursementLayers = function () {
            const mapLayers = self.mapInstance.getStyle().layers;
            let layerRemoved = false;
            mapLayers.forEach(function (layer) {
                if (layer.id.includes(DISBURSEMENT_LAYER_PREFIX)) {
                    self.mapInstance.removeLayer(layer.id);
                    layerRemoved = true;
                }
            });
            return layerRemoved;
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
        self.oldSelectedSavedPolygonId = ko.observable('');
        self.resettingSavedPolygon = false;
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

        self.selectedSavedPolygonId.subscribe(function (selectedPolygonID) {
            self.oldSelectedSavedPolygonId(selectedPolygonID);
        }, null, "beforeChange");

        self.selectedSavedPolygonId.subscribe(() => {
            // avoid running actions expected on user interactions if resetting saved polygon
            // and update resettingSavedPolygon back to false
            if (self.resettingSavedPolygon) {
                self.resettingSavedPolygon = false;
                return;
            }

            const selectedId = parseInt(self.selectedSavedPolygonId());
            const polygonObj = self.savedPolygons().find(
                function (o) { return o.id === selectedId; }
            );
            if (!polygonObj) {
                return;
            }

            // hide it by default and show it only if necessary
            $('#disbursement-clear-message').hide();
            if (mapObj.hasDisbursementLayers()) {
                let confirmation = confirm(
                    gettext("Warning! This action will clear the current disbursement. " +
                            "Please confirm if you want to proceed.")
                );
                if (confirmation) {
                    if (mapObj.removeDisbursementLayers()) {
                        $('#disbursement-clear-message').show();
                    }
                } else {
                    // set flag
                    self.resettingSavedPolygon = true;
                    self.selectedSavedPolygonId(self.oldSelectedSavedPolygonId());
                    return;
                }
            }
            self.clearActivePolygon();

            removeActivePolygonLayer();
            createActivePolygonLayer(polygonObj);

            self.activeSavedPolygon = polygonObj;
            self.addPolygonsToFilterList(polygonObj.geoJson.features);
            self.btnExportDisabled(false);
            self.btnSaveDisabled(true);
            if (self.shouldSelectAfterFilter) {
                const features = polygonObj.geoJson.features.concat(mapObj.drawControls.getAll().features);
                self.mapObj.selectAllMapItems(features);
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
