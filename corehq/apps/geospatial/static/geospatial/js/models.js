
hqDefine('geospatial/js/models', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'geospatial/js/utils',
    'hqwebapp/js/bootstrap3/alert_user',
    'mapbox-gl',
    '@mapbox/mapbox-gl-draw',
    '@turf/turf',
    'hqwebapp/js/components/pagination',
], function (
    $,
    ko,
    _,
    initialPageData,
    utils,
    alertUser,
    mapboxgl,
    MapboxDraw,
    turf,
) {
    const FEATURE_QUERY_PARAM = 'features';
    const SELECTED_FEATURE_ID_QUERY_PARAM = 'selected_feature_id';
    const DEFAULT_CENTER_COORD = [-20.0, -0.0];
    const DISBURSEMENT_LAYER_PREFIX = 'route-';
    const unexpectedErrorMessage = gettext(
        "Oops! Something went wrong!" +
        " Please report an issue if the problem persists.",
    );
    const caseMarkerColors = {
        'default': "#808080", // Gray
        'selected': "#00FF00", // Green
    };
    const userMarkerColors = {
        'default': "#0e00ff", // Blue
        'selected': "#0b940d", // Dark Green
    };

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

    var MapItem = function (data, mapModel) {
        let self = this;
        self.itemId = data.id;
        self.name = data.name;
        self.coordinates = data.coordinates;
        self.itemType = data.itemType;
        self.link = data.link;
        self.selectCssId = `select_${self.itemId}`;
        self.isSelected = ko.observable(data.isSelected);
        self.mapModel = mapModel;
        self.customData = data.customData;

        self.getItemType = function () {
            if (self.itemType === 'user') {
                return gettext("Mobile Worker");
            }
            return gettext("Case");
        };

        function changeMarkerColor(val) {
            self.mapModel.updatePropertyInSource(self.itemId, 'selected', val);
            self.mapModel.refreshSource();
        }

        self.updateCheckbox = function () {
            const checkbox = $(`#${self.selectCssId}`);
            if (!checkbox) {
                return;
            }
            checkbox.prop('checked', self.isSelected());
        };

        self.isSelected.subscribe(function () {
            self.updateCheckbox();
            const isSelected = self.isSelected().toString();
            changeMarkerColor(isSelected);
        });

        self.getJson = function () {
            return {
                'id': self.itemId,
                'text': self.name,
            };
        };

        self.getGeoJson = function () {
            return {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [
                        self.coordinates.lng,
                        self.coordinates.lat,
                    ],
                },
                'properties': {
                    'selected': self.isSelected().toString(),  // Can only use numbers and strings, so use a str to represent true/false
                    'id': self.itemId,
                    'type': self.itemType,
                },
            };
        };
    };

    var GroupedCaseMapItem = function (itemId, itemData, link) {
        let self = this;
        self.itemId = itemId;
        self.itemData = itemData;
        self.link = link;
        self.groupId = null;
        self.groupCoordinates = null;
        self.coordinates = itemData.coordinates;

        self.toJson = function () {
            const coordinates = (self.coordinates) ? `${self.coordinates.lng} ${self.coordinates.lat}` : "";
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

        self.userLayerName = 'user-points';
        self.caseLayerName = 'case-points';
        self.dataPointsSourceName = 'data-points';
        self.sourceData = {
            'type': 'FeatureCollection',
            'features': [],
        };

        self.usesClusters = usesClusters;
        self.usesStreetsLayers = usesStreetsLayers;

        self.mapInstance;
        self.drawControls;

        self.caseMapItems = ko.observableArray([]);
        self.userMapItems = ko.observableArray([]);

        self.caseGroupsIndex = {};

        self.DISBURSEMENT_LINES_LAYER_ID = 'disbursement-lines';

        self.initMap = function (mapDivId, centerCoordinates, disableDrawControls) {
            mapboxgl.accessToken = initialPageData.get('mapbox_access_token');
            if (!centerCoordinates) {
                centerCoordinates = [-91.874, 42.76]; // should be domain specific
            }

            self.mapInstance = new mapboxgl.Map({
                container: mapDivId, // container ID
                style: 'mapbox://styles/mapbox/streets-v12', // style URL
                center: centerCoordinates, // starting position [lng, lat]
                zoom: 12,
                attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                             ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            });

            if (!disableDrawControls) {
                self.drawControls = new MapboxDraw({
                    // API: https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md
                    displayControlsDefault: false,
                    boxSelect: true, // enables box selection
                    controls: {
                        polygon: true,
                        trash: true,
                    },
                });
                self.mapInstance.addControl(self.drawControls);
            }

            // Add zoom and rotation controls to the map.
            self.mapInstance.addControl(new mapboxgl.NavigationControl());

            if (self.usesClusters) {
                createClusterLayers();
            } else {
                self.mapInstance.on('load', createMarkerLayers);
            }

            if (self.usesStreetsLayers) {
                loadMapBoxStreetsLayers();
                addLayersToPanel();
            }
        };

        self.addDataToSource = function (features) {
            self.sourceData.features = self.sourceData.features.concat(features);
            self.refreshSource();
        };

        self.removeItemTypeFromSource = function (itemType) {
            self.sourceData.features = self.sourceData.features.filter(
                feature => feature.properties.type !== itemType,
            );
            self.refreshSource();
        };

        self.refreshSource = function () {
            let source = self.mapInstance.getSource(self.dataPointsSourceName);
            if (!source) {
                return;
            }
            source.setData(self.sourceData);
        };

        self.updatePropertyInSource = function (itemId, propName, propVal) {
            const featureIndex = self.sourceData.features.findIndex(feature => feature.properties.id === itemId);
            if (featureIndex >= 0) {
                self.sourceData.features[featureIndex].properties[propName] = propVal;
                self.refreshSource();
            }
        };

        function createMarkerLayers() {
            self.mapInstance.addSource(self.dataPointsSourceName, {
                'type': 'geojson',
                'data': self.sourceData,
            });

            self.mapInstance.loadImage(
                'https://docs.mapbox.com/mapbox-gl-js/assets/custom_marker.png',
                (error, image) => {
                    if (error) {
                        alertUser.alert_user(unexpectedErrorMessage, 'danger');
                        return;
                    }
                    self.mapInstance.addImage('custom-marker', image, {sdf: true});
                    self.createMarkerLayer('case-points', self.dataPointsSourceName, 'case', caseMarkerColors.default, caseMarkerColors.selected);
                    self.mapInstance.on('click', 'case-points', (e) => {
                        markerClickEvent(e, 'case');
                    });
                    self.createMarkerLayer('user-points', self.dataPointsSourceName, 'user', userMarkerColors.default, userMarkerColors.selected);
                    self.mapInstance.on('click', 'user-points', (e) => {
                        markerClickEvent(e, 'user');
                    });
                },
            );
        }

        self.createMarkerLayer = function (layerName, source, itemType, defaultColor, selectedColor) {
            self.mapInstance.addLayer({
                'id': layerName,
                'type': 'symbol',
                'source': source,
                'layout': {
                    'icon-image': 'custom-marker',
                    'icon-size': [
                        'interpolate',
                        ['exponential', 2],
                        ['zoom'],
                        5, 0.35,
                        15, 3,
                    ],
                    'icon-allow-overlap': true,
                },
                'paint': {
                    'icon-color': [
                        'match',
                        ['get', 'selected'],
                        'false',
                        defaultColor,
                        'true',
                        selectedColor,
                        '#0000FF',
                    ],
                },
                'filter': ['==', ['get', 'type'], itemType],
            });
        };

        function markerClickEvent(e, itemType) {
            const coordinates = e.features[0].geometry.coordinates.slice();
            const markerId = e.features[0].properties.id;

            // Ensure that if the map is zoomed out such that multiple
            // copies of the feature are visible, the popup appears
            // over the copy being pointed to.
            if (['mercator', 'equirectangular'].includes(self.mapInstance.getProjection().name)) {
                while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
                    coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
                }
            }

            const popupDiv = document.createElement('div');
            const markerItems = (itemType === 'user') ? self.userMapItems() : self.caseMapItems();
            const mapItem = markerItems.find((mapItem) => {
                return markerId === mapItem.itemId;
            });

            const openFunc = () => mapItem.updateCheckbox();
            const popup = utils.createMapPopup(coordinates, popupDiv, openFunc);
            popup.addTo(self.mapInstance);
            $(popupDiv).koApplyBindings(mapItem);
        }

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
            const isSelected = self.isMapItemInPolygons(polygonArr, mapItem.coordinates);
            mapItem.isSelected(isSelected);
        };

        self.isMapItemInPolygons = function (polygonFeatures, coordinates) {
            for (const polygon of polygonFeatures) {
                if (polygon.geometry.type !== 'Polygon') {
                    continue;
                }
                // Will be 0 if a user deletes a point from a three-point polygon,
                // since mapbox will delete the entire polygon. turf.booleanPointInPolygon()
                // does not expect this, and will raise a 'TypeError' exception.
                if (!polygon.geometry.coordinates.length) {
                    continue;
                }
                const coordinatesArr = [coordinates.lng, coordinates.lat];
                const point = turf.point(coordinatesArr);  // eslint-disable-line no-undef
                if (turf.booleanPointInPolygon(point, polygon.geometry)) {
                    return true;
                }
            }
            return false;
        };

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
            const firstCoord = mapItems[0].coordinates;
            const bounds = mapItems.reduce(function (bounds, mapItem) {
                const coord = mapItem.coordinates;
                if (coord) {
                    return bounds.extend(coord);
                }
            }, new mapboxgl.LngLatBounds(firstCoord, firstCoord));

            self.mapInstance.fitBounds(bounds, {
                padding: 50,  // in pixels
                duration: 500,  // in ms
                maxZoom: 10,  // 0-23
            });
        };

        self.hasDisbursementLayer = function () {
            return self.mapInstance.getLayer(self.DISBURSEMENT_LINES_LAYER_ID);
        };

        self.addDisbursementLinesLayer = function (source) {
            let layerId = self.DISBURSEMENT_LINES_LAYER_ID;
            self.mapInstance.addSource(layerId, {
                'type': 'geojson',
                'data': source,
            });
            self.mapInstance.addLayer({
                id: layerId,
                type: 'line',
                source: layerId,
                layout: {
                    'line-join': 'round',
                    'line-cap': 'round',
                },
                paint: {
                    'line-color': '#808080',
                    'line-width': 1,
                },
            });
        };

        self.removeDisbursementLayer = function () {
            if (self.mapInstance.getLayer(self.DISBURSEMENT_LINES_LAYER_ID)) {
                self.mapInstance.removeLayer(self.DISBURSEMENT_LINES_LAYER_ID);
            }
            if (self.mapInstance.getSource(self.DISBURSEMENT_LINES_LAYER_ID)) {
                self.mapInstance.removeSource(self.DISBURSEMENT_LINES_LAYER_ID);
            }
        };

        self.hasSelectedUsers = function () {
            return self.userMapItems().some((userMapItem) => {
                return userMapItem.isSelected();
            });
        };

        self.hasSelectedCases = function () {
            return self.caseMapItems().some((caseMapItem) => {
                return caseMapItem.isSelected();
            });
        };
    };

    var PolygonFilter = function (mapObj, shouldUpdateQueryParam, shouldSelectAfterFilter, requiresPageRefresh) {
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
        self.requiresPageRefresh = ko.observable(requiresPageRefresh);  // If true then actions such as adding or moving a polygon requires a page refresh
        self.hasUrlError = ko.observable(false);

        self.savedPolygons = ko.observableArray([]);
        self.selectedSavedPolygonId = ko.observable('');
        self.oldSelectedSavedPolygonId = ko.observable('');
        self.resettingSavedPolygon = false;
        self.activeSavedPolygon = ko.observable(null);

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
            let success;
            if (Object.keys(self.polygons)) {
                success = utils.setQueryParam(FEATURE_QUERY_PARAM, JSON.stringify(self.polygons));
            } else {
                success = utils.clearQueryParam(FEATURE_QUERY_PARAM);
            }
            self.shouldRefreshPage(success && self.requiresPageRefresh());
            self.hasUrlError(!success);
        }

        function updateSelectedSavedPolygonParam() {
            const url = new URL(window.location.href);
            const prevSelectedId = url.searchParams.get(SELECTED_FEATURE_ID_QUERY_PARAM);
            if (prevSelectedId === self.selectedSavedPolygonId()) {
                // If the user refreshes the page, we shouldn't prompt another refresh
                return;
            }

            let success;
            if (self.selectedSavedPolygonId()) {
                success = utils.setQueryParam(SELECTED_FEATURE_ID_QUERY_PARAM, self.selectedSavedPolygonId());
            } else {
                success = utils.clearQueryParam(SELECTED_FEATURE_ID_QUERY_PARAM);
            }
            self.shouldRefreshPage(success && self.requiresPageRefresh());
            self.hasUrlError(!success);
        }

        self.loadPolygonFromQueryParam = function () {
            const featureParam = utils.fetchQueryParam(FEATURE_QUERY_PARAM);
            if (featureParam) {
                const features = JSON.parse(featureParam);
                for (const featureId in features) {
                    const feature = features[featureId];
                    self.mapObj.drawControls.add(feature);
                    self.polygons[featureId] = feature;
                }
            }
        };

        self.loadSelectedPolygonFromQueryParam = function () {
            const selectedFeatureParam = utils.fetchQueryParam(SELECTED_FEATURE_ID_QUERY_PARAM);
            if (selectedFeatureParam) {
                self.selectedSavedPolygonId(selectedFeatureParam);
            }
        };

        function removeActivePolygonLayer() {
            if (self.activeSavedPolygon()) {
                const layerName = self.activeSavedPolygon().id + '-layer';
                const sourceName = self.activeSavedPolygon().id + '-source';
                self.mapObj.mapInstance.removeLayer(layerName);
                self.mapObj.mapInstance.removeSource(sourceName);
            }
        }

        function createActivePolygonLayer(polygonObj) {
            const layerName = String(polygonObj.id) + '-layer';
            const sourceName = String(polygonObj.id) + '-source';
            self.mapObj.mapInstance.addSource(
                sourceName,
                {'type': 'geojson', 'data': polygonObj.geoJson},
            );
            self.mapObj.mapInstance.addLayer({
                'id': layerName,
                'type': 'fill',
                'source': sourceName,
                'layout': {},
                'paint': {
                    'fill-color': '#0080ff',
                    'fill-opacity': 0.5,
                },
            });
        }

        self.clearActivePolygon = function () {
            if (self.activeSavedPolygon()) {
                removeActivePolygonLayer();
                self.activeSavedPolygon(null);
                self.btnSaveDisabled(false);
                self.btnExportDisabled(true);
            }
        };

        self.clearSelectedPolygonFilter = function () {
            if (!clearDisbursementBeforeProceeding()) {
                return;
            }

            self.selectedSavedPolygonId('');
            self.clearActivePolygon();
            updateSelectedSavedPolygonParam();
            const features = mapObj.drawControls.getAll().features;
            self.mapObj.selectAllMapItems(features);
        };

        function clearDisbursementBeforeProceeding() {
            let proceedFurther = true;
            if (self.mapObj.hasDisbursementLayer()) {
                // hide it by default and show it only if necessary
                $('#disbursement-clear-message').hide();
                if (confirmForClearingDisbursement()) {
                    self.mapObj.removeDisbursementLayer();
                    $('#disbursement-clear-message').show();
                    $('#disbursement-params').hide();
                } else {
                    proceedFurther = false;
                }
            }
            return proceedFurther;
        }

        function confirmForClearingDisbursement() {
            return confirm(
                gettext("Warning! This action will clear the current disbursement. " +
                        "Please confirm if you want to proceed."),
            );
        }

        self.exportSelectedPolygonGeoJson = function (data, event) {
            if (self.activeSavedPolygon()) {
                const convertedData = 'application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(self.activeSavedPolygon().geoJson));
                $(event.target).attr('href', 'data:' + convertedData);
                $(event.target).attr('download',self.activeSavedPolygon().text + '.geojson');
                return true;
            }
            return false;
        };

        self.deleteSelectedPolygonFilter = function () {
            if (!clearDisbursementBeforeProceeding()) {
                return;
            }

            const deleteGeoJSONUrl = initialPageData.reverse('geo_polygon', self.selectedSavedPolygonId());
            $.ajax({
                type: 'DELETE',
                url: deleteGeoJSONUrl,
                success: function (ret) {
                    if (!ret.success) {
                        return alertUser.alert_user(ret.message, 'danger');
                    }
                    self.clearSelectedPolygonFilter();
                    var message = ret.message + " " + gettext("Refreshing Page...");
                    alertUser.alert_user(message, 'success');
                    setTimeout(function () {
                        window.location.reload();
                    }, 2000);
                },
                error: function () {
                    alertUser.alert_user(unexpectedErrorMessage, 'danger');
                },
            });
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
                function (o) { return o.id === selectedId; },
            );
            if (!polygonObj) {
                return;
            }

            if (!clearDisbursementBeforeProceeding()) {
                // set flag
                self.resettingSavedPolygon = true;
                self.selectedSavedPolygonId(self.oldSelectedSavedPolygonId());
                return;
            }

            self.clearActivePolygon();

            createActivePolygonLayer(polygonObj);

            self.activeSavedPolygon(polygonObj);
            updateSelectedSavedPolygonParam();
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
            self.loadSelectedPolygonFromQueryParam();
        };

        self.saveGeoPolygon = function () {
            let data = self.mapObj.drawControls.getAll();
            if (data.features.length) {
                const name = window.prompt(gettext("Name of the Area"));
                if (!validateSavedPolygonName(name)) {
                    return;
                }
                const saveGeoPolygonUrl = initialPageData.reverse('geo_polygons');

                if (!clearDisbursementBeforeProceeding()) {
                    return;
                }

                data['name'] = name;
                $.ajax({
                    type: 'post',
                    url: saveGeoPolygonUrl,
                    dataType: 'json',
                    data: JSON.stringify({'geo_json': data}),
                    contentType: "application/json; charset=utf-8",
                    success: function (ret) {
                        delete data.name;
                        // delete drawn area
                        self.mapObj.drawControls.deleteAll();
                        self.removePolygonsFromFilterList(data.features);
                        self.savedPolygons.push(
                            new SavedPolygon({
                                name: name,
                                id: ret.id,
                                geo_json: data,
                            }),
                        );
                        // redraw using mapControlsModelInstance
                        self.selectedSavedPolygonId(ret.id);
                        self.shouldRefreshPage(true);
                    },
                    error: function (response) {
                        const responseText = response.responseText;
                        if (responseText) {
                            alertUser.alert_user(responseText, 'danger');
                        } else {
                            alertUser.alert_user(unexpectedErrorMessage, 'danger');
                        }
                    },
                });
            }
        };

        function validateSavedPolygonName(name) {
            if (name === null) {
                return false;
            }
            if (name === '') {
                alertUser.alert_user(gettext("Please enter the name for the area!"), 'warning', false, true);
                return false;
            }
            return true;
        }
    };

    var AssignmentRow = function (caseName, caseId, userId, userName, userPrimaryLocName, mapItem) {
        let self = this;

        self.caseName = ko.observable(caseName);
        self.caseId = caseId;
        self.assignedUsername = ko.observable(userName);
        self.assignedUserId = userId;
        self.assignedUserPrimaryLocName = ko.observable(userPrimaryLocName);
        self.mapItem = mapItem;
        self.isSelected = ko.observable(false);

        self.getJson = function () {
            return {
                caseName: self.caseName(),
                caseId: self.caseId,
                assignedUsername: self.assignedUsername(),
                assignedUserId: self.assignedUserId,
                assignedUserPrimaryLocName: self.assignedUserPrimaryLocName(),
            };
        };

        return self;
    };

    var AssignmentManager = function (mapModel, disbursementModel) {
        let self = this;

        const emptyColStr = '---';

        self.itemsPerPage = ko.observable(5);
        self.totalItems = ko.observable(0);
        self.currentPage = ko.observable(1);

        self.mapModel = mapModel;
        self.disbursementModel = disbursementModel;

        self.caseData = [];
        self.filteredCaseData = ko.observableArray([]);
        self.caseDataPage = ko.computed(function () {
            const end = self.currentPage() * self.itemsPerPage();
            const start = end - self.itemsPerPage();
            return self.filteredCaseData().slice(start, end);
        });

        self.userData = ko.observableArray([]);
        self.canOpenModal = ko.computed(function () {
            return self.mapModel.caseGroupsIndex.length;
        });

        self.selectedUserId = ko.observable();
        self.includeRelatedCases = ko.observable(false);

        self.assignedFilter = ko.observable();
        self.assignedFilter.subscribe(() => {
            if (self.assignedFilter() === 'all') {
                self.filteredCaseData(self.caseData);
            } else {
                self.filteredCaseData(self.caseData.filter(function (caseItem) {
                    if (self.assignedFilter() === 'unassigned') {
                        return !caseItem.assignedUserId;
                    }
                    return caseItem.assignedUserId;
                }));
            }
            self.totalItems(self.filteredCaseData().length);
        });

        self.hasCheckedRows = ko.computed(function () {
            return _.some(self.caseDataPage(), function (caseItem) {
                return caseItem.isSelected();
            });
        });

        self.isAllChecked = ko.observable(false);
        self.toggleSelectAll = function (selectAll) {
            self.isAllChecked(selectAll);
            for (const caseItem of self.caseDataPage()) {
                caseItem.isSelected(self.isAllChecked());
            }
        };

        self.loadCaseData = function () {
            const groupData = self.mapModel.caseGroupsIndex;
            self.caseData = [];
            for (const item of self.mapModel.caseMapItems()) {
                const assignedUserId = (groupData[item.itemId]) ? groupData[item.itemId].assignedUserId : null;
                let assignedUsername = emptyColStr;
                let primaryLocName = emptyColStr;
                if (assignedUserId) {
                    const userData = groupData[assignedUserId].item;
                    assignedUsername = userData.name;
                    primaryLocName = userData.customData.primary_loc_name;
                }
                self.caseData.push(
                    new AssignmentRow(
                        item.name, item.itemId, assignedUserId, assignedUsername, primaryLocName, item,
                    ),
                );
            }

            loadUserData();
            self.filteredCaseData(self.caseData);
            self.totalItems(self.filteredCaseData().length);
        };

        function loadUserData() {
            self.userData([]);
            for (const item of self.mapModel.userMapItems()) {
                self.userData.push(item.getJson());
            }

            $('#user-assignment-select').select2({
                placeholder: gettext('No user selected (unassign mode)'),
                allowClear: true,
                data: self.userData(),
            }).val(null).trigger('change');
        }

        self.goToPage = function (pageNumber) {
            self.toggleSelectAll(false);
            self.currentPage(pageNumber);
        };

        self.assignUserToCases = function () {
            let selectedUser;
            if (self.selectedUserId()) {
                selectedUser = self.mapModel.caseGroupsIndex[self.selectedUserId()].item;
            }
            for (const caseItem of self.caseDataPage()) {
                if (!caseItem.isSelected()) {
                    continue;
                }

                caseItem.assignedUsername(
                    (selectedUser) ? selectedUser.name : emptyColStr,
                );
                caseItem.assignedUserPrimaryLocName(
                    (selectedUser) ? selectedUser.customData.primary_loc_name : emptyColStr,
                );
                caseItem.assignedUserId = self.selectedUserId();
                caseItem.isSelected(false);
            }
        };

        self.finishAssignment = function () {
            for (const caseItem of self.caseData) {
                const userItem = self.mapModel.caseGroupsIndex[caseItem.assignedUserId];
                if (userItem) {
                    self.mapModel.caseGroupsIndex[caseItem.caseId] = {
                        assignedUserId: caseItem.assignedUserId,
                        groupId: userItem.groupId,
                        item: caseItem.mapItem,
                    };
                } else if (self.mapModel.caseGroupsIndex[caseItem.caseId]) {
                    delete self.mapModel.caseGroupsIndex[caseItem.caseId];
                }
            }

            self.mapModel.removeDisbursementLayer();
            self.disbursementModel.connectUserWithCasesOnMap();
        };

        self.exportAssignments = function () {
            const headers = [
                gettext('Case Name'),
                gettext('Case ID'),
                gettext('Assigned User ID'),
                gettext('Assigned Username'),
                gettext('Assigned User Primary Location'),
            ];
            const cols = [
                'caseName',
                'caseId',
                'assignedUserId',
                'assignedUsername',
                'assignedUserPrimaryLocName',
            ];
            const casesToExport = self.filteredCaseData().map(function (caseItem) {
                return caseItem.getJson();
            });
            utils.downloadCsv(casesToExport, headers, cols, 'Case Assignment Export');
        };

        self.assignmentAjaxInProgress = ko.observable(false);
        self.acceptAssignments = function () {
            let caseIdToOwnerId = {};
            for (const caseItem of self.mapModel.caseMapItems()) {
                const caseData = self.mapModel.caseGroupsIndex[caseItem.itemId];
                if (caseData && caseData.assignedUserId) {
                    caseIdToOwnerId[caseData.item.itemId] = caseData.assignedUserId;
                }
            }
            let requestData = {
                'case_id_to_owner_id': caseIdToOwnerId,
                'include_related_cases': self.includeRelatedCases(),
            };
            const reassignCasesUrl = initialPageData.reverse('reassign_cases');
            self.assignmentAjaxInProgress(true);
            $.ajax({
                type: 'post',
                url: reassignCasesUrl,
                dataType: 'json',
                data: JSON.stringify(requestData),
                contentType: "application/json; charset=utf-8",
                success: function (response) {
                    if (!response.success) {
                        return alertUser.alert_user(response.message, 'danger');
                    }
                    alertUser.alert_user(response.message, 'success', false, true);
                },
                error: function (response) {
                    const responseText = response.responseText;
                    if (responseText) {
                        alertUser.alert_user(responseText, 'danger');
                    } else {
                        alertUser.alert_user(unexpectedErrorMessage, 'danger', false, true);
                    }
                },
                complete: function () {
                    self.assignmentAjaxInProgress(false);
                },
            });
        };

        return self;
    };

    return {
        MissingGPSModel: MissingGPSModel,
        SavedPolygon: SavedPolygon,
        MapItem: MapItem,
        GroupedCaseMapItem: GroupedCaseMapItem,
        Map: Map,
        PolygonFilter: PolygonFilter,
        AssignmentManager: AssignmentManager,
    };
});
