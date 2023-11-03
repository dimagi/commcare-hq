hqDefine("geospatial/js/case_grouping_map",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/alert_user',
], function (
    $,
    ko,
    _,
    initialPageData,
    alertUser
) {

    const MAPBOX_LAYER_VISIBILITY = {
        None: 'none',
        Visible: 'visible',
    };

    const DEFAULT_MARKER_COLOR = "rgba(128,128,128,0.25)";
    const MAP_CONTAINER_ID = 'case-grouping-map';
    let mapDrawControls;
    const clusterStatsInstance = new clusterStatsModel();
    let exportModelInstance;
    let mapMarkers = [];

    let polygonFilterInstance;
    const FEATURE_QUERY_PARAM = 'features';

    function caseModel(caseId, coordinates, caseLink) {
        'use strict';
        var self = {};
        self.caseId = caseId;
        self.coordinates = coordinates;
        self.caseLink = caseLink;
        self.groupId = null;
        self.groupCoordinates = null;

        self.toJson = function () {
            const coordinates = (self.coordinates) ? `${self.coordinates.lng} ${self.coordinates.lat}` : "";
            const groupCoordinates = (self.groupCoordinates) ? `${self.groupCoordinates.lng} ${self.groupCoordinates.lat}` : "";
            return {
                'groupId': self.groupId,
                'groupCenterCoordinates': groupCoordinates,
                'caseId': self.caseId,
                'coordinates': coordinates,
            };
        }

        return self;
    }

    function clusterStatsModel() {
        'use strict';
        let self = {};
        self.totalClusters = ko.observable(0);
        self.clusterMinCount = ko.observable(0);
        self.clusterMaxCount = ko.observable(0);
        return self;
    }

    function exportModel() {
        var self = {};

        self.casesToExport = ko.observableArray([]);

        self.downloadCSV = function () {
            if (!self.casesToExport().length) {
                return;
            }

            const casesToExport = _.map(self.casesToExport(), function (caseItem) {
                return caseItem.toJson();
            });

            let csvStr = "";

            // Write headers first
            csvStr = Object.keys(casesToExport[0]).join(",");
            csvStr += "\n";

            _.forEach(casesToExport, function (itemRow) {
                csvStr += Object.keys(itemRow).map(key => itemRow[key]).join(",");
                csvStr += "\n";
            });

            // Download CSV file
            const hiddenElement = document.createElement('a');
            hiddenElement.href = 'data:text/csv;charset=utf-8,' + encodeURI(csvStr);
            hiddenElement.target = '_blank';
            hiddenElement.download = `Grouped Cases (${getTodayDate()}).csv`;
            hiddenElement.click();
            hiddenElement.remove();
        };

        self.loadCaseGroups = function(caseGroups) {
            self.casesToExport().forEach(caseItem => {
                const groupData = caseGroups[caseItem.caseId];
                if (groupData !== undefined) {
                    caseItem.groupId = groupData.groupId;
                    caseItem.groupCoordinates = groupData.groupCoordinates;
                }
            });
        }

        self.clearCaseGroups = function() {
            self.casesToExport().forEach(caseItem => {
                if (caseItem.groupId) {
                    caseItem.groupId = null;
                    caseItem.groupCoordinates = null;
                }
            });
        }
        return self;
    }

    function polygonModel(polygon) {
        let self = {};
        self.text = polygon.name;
        self.id = polygon.id;
        self.geoJson = polygon.geo_json;
        return self;
    }

    function polygonFilterModel() {
        let self = {};
        self.polygons = {};
        self.shouldRefreshPage = ko.observable(false);

        self.savedPolygons = ko.observableArray();
        self.selectedSavedPolygonId = ko.observable('');
        self.activeSavedPolygon;

        self.addPolygonsToFilterList = function (featureList) {
            for (const feature of featureList) {
                self.polygons[feature.id] = feature;
            }
            updatePolygonQueryParam();
        };

        self.removePolygonsFromFilterList = function (featureList) {
            for (const feature of featureList) {
                if (self.polygons[feature.id]) {
                    delete self.polygons[feature.id];
                }
            }
            updatePolygonQueryParam();
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

        function removeActivePolygonLayer() {
            if (self.activeSavedPolygon) {
                map.removeLayer(self.activeSavedPolygon.id);
                map.removeSource(self.activeSavedPolygon.id);
            }
        }

        function createActivePolygonLayer(polygonObj) {
            map.addSource(
                String(polygonObj.id),
                {'type': 'geojson', 'data': polygonObj.geoJson}
            );
            map.addLayer({
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
            self.selectedSavedPolygonId('');
            self.removePolygonsFromFilterList(self.activeSavedPolygon.geoJson.features);
            removeActivePolygonLayer();
            self.activeSavedPolygon = null;
        };

        self.selectedSavedPolygonId.subscribe(() => {
            const selectedId = parseInt(self.selectedSavedPolygonId());
            const polygonObj = self.savedPolygons().find(
                function (o) { return o.id === selectedId; }
            );
            if (!polygonObj) {
                return;
            }

            if (self.activeSavedPolygon) {
                self.clearActivePolygon();
            }

            removeActivePolygonLayer();
            createActivePolygonLayer(polygonObj);

            self.activeSavedPolygon = polygonObj;
            self.addPolygonsToFilterList(polygonObj.geoJson.features);
        });

        self.loadPolygons = function (polygonArr) {
            self.savedPolygons([]);
            _.each(polygonArr, (polygon) => {
                // Saved features don't have IDs, so we need to give them to uniquely identify them for polygon filtering
                for (const feature of polygon.geo_json.features) {
                    feature.id = uuidv4();
                }
                self.savedPolygons.push(polygonModel(polygon));
            });
        };

        return self;
    }

    function getTodayDate() {
        const todayDate = new Date();
        return todayDate.toLocaleDateString();
    }

    function initMap() {
        'use strict';

        mapboxgl.accessToken = initialPageData.get('mapbox_access_token'); // eslint-disable-line no-undef
        const centerCoordinates = [2.43333330, 9.750];

        const mapboxInstance = new mapboxgl.Map({  // eslint-disable-line no-undef
            container: MAP_CONTAINER_ID, // container ID
            style: 'mapbox://styles/mapbox/streets-v12', // style URL
            center: centerCoordinates, // starting position [lng, lat]
            zoom: 6,
            attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                         ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        });

        mapboxInstance.on('load', () => {
            map.addSource('caseWithGPS', {
                type: 'geojson',
                data: {
                    "type": "FeatureCollection",
                    "features": [],
                },
                cluster: true,
                clusterMaxZoom: 14, // Max zoom to cluster points on
                clusterRadius: 50, // Radius of each cluster when clustering points (defaults to 50)
            });
            map.addLayer({
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
            map.addLayer({
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
            map.addLayer({
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

        mapDrawControls = new MapboxDraw({  // eslint-disable-line no-undef
            // API: https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md
            displayControlsDefault: false,
            boxSelect: true,
            controls: {
                polygon: true,
                trash: true,
            },
        });
        mapboxInstance.addControl(mapDrawControls);

        mapboxInstance.on('moveend', updateClusterStats);
        mapboxInstance.on('draw.update', (e) => polygonFilterInstance.addPolygonsToFilterList(e.features));
        mapboxInstance.on('draw.create', (e) => polygonFilterInstance.addPolygonsToFilterList(e.features));
        mapboxInstance.on('draw.delete', (e) => polygonFilterInstance.removePolygonsFromFilterList(e.features));

        return mapboxInstance;
    }

    function updateClusterStats() {
        const sourceFeatures = map.querySourceFeatures('caseWithGPS', {
            sourceLayer: 'clusters',
            filter: ['==', 'cluster', true],
        });

        // Mapbox clustering creates the same cluster groups with slightly different coordinates.
        // Seems to be related to keeping track of clusters at different zoom levels.
        // There could therefore be more than one cluster that share the same ID so we should keep track
        // of these to skip them if we've gone over them already
        let uniqueClusterIds = {};
        let clusterStats = {
            total: 0,
            min: 0,
            max: 0,
        };
        for (const clusterFeature of sourceFeatures) {
            // Skip over duplicate clusters
            if (uniqueClusterIds[clusterFeature.id]) {
                continue;
            }

            uniqueClusterIds[clusterFeature.id] = true;
            clusterStats.total++;
            const pointCount = clusterFeature.properties.point_count;
            if (pointCount < clusterStats.min || clusterStats.min === 0) {
                clusterStats.min = pointCount;
            }
            if (pointCount > clusterStats.max) {
                clusterStats.max = pointCount;
            }
        }
        clusterStatsInstance.totalClusters(clusterStats.total);
        clusterStatsInstance.clusterMinCount(clusterStats.min);
        clusterStatsInstance.clusterMaxCount(clusterStats.max);
    }

    function loadMapClusters(caseList) {
        let caseLocationsGeoJson = {
            "type": "FeatureCollection",
            "features": [],
        };

        _.each(caseList, function (caseWithGPS) {
            const coordinates = caseWithGPS.coordinates;
            if (coordinates && coordinates.lat && coordinates.lng) {
                caseLocationsGeoJson["features"].push(
                    {
                        "type": "feature",
                        "properties": {
                            "id": caseWithGPS.caseId,
                        },
                        "geometry": {
                            "type": "Point",
                            "coordinates": [coordinates.lng, coordinates.lat],
                        },
                    },
                );
            }
        });

        if (map.getSource('caseWithGPS')) {
            map.getSource('caseWithGPS').setData(caseLocationsGeoJson);
        } else {
            map.on('load', () => {
                map.getSource('caseWithGPS').setData(caseLocationsGeoJson);
            });
        }
    }

    function getClusterLeavesAsync(clusterSource, clusterId, pointCount) {
        return new Promise((resolve, reject) => {
            clusterSource.getClusterLeaves(clusterId, pointCount, 0, (error, casePoints) => {
                if (error) {
                    reject(error);
                } else {
                    resolve(casePoints);
                }
            });
        });
    }

    function setMapLayersVisibility(visibility) {
        map.setLayoutProperty('clusters', 'visibility', visibility);
        map.setLayoutProperty('cluster-count', 'visibility', visibility);
        map.setLayoutProperty('unclustered-point', 'visibility', visibility);
    }

    function getRandomRGBColor() {
        var r = Math.floor(Math.random() * 256); // Random value between 0 and 255 for red
        var g = Math.floor(Math.random() * 256); // Random value between 0 and 255 for green
        var b = Math.floor(Math.random() * 256); // Random value between 0 and 255 for blue

        return `rgba(${r},${g},${b},1)`;
    }

    function collapseGroupsOnMap() {
        setMapLayersVisibility(MAPBOX_LAYER_VISIBILITY.None);
        var groupColors = {};

        exportModelInstance.casesToExport().forEach(function (caseItem) {
            if (!caseItem.coordinates) {
                return;
            }

            const groupId = caseItem.groupId;
            let color = DEFAULT_MARKER_COLOR;

            if (groupId) {
                if (groupColors[groupId] === undefined) {
                    groupColors[groupId] = getRandomRGBColor();
                }
                color = groupColors[groupId];
            }
            const marker = new mapboxgl.Marker({ color: color, draggable: false });  // eslint-disable-line no-undef
            marker.setLngLat([caseItem.coordinates.lng, caseItem.coordinates.lat]);

            // Add the marker to the map
            marker.addTo(map);
            mapMarkers.push(marker);
        });
    }

    function uuidv4() {
        // https://stackoverflow.com/questions/105034/how-do-i-create-a-guid-uuid/2117523#2117523
        return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
            (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16),
        );
    }

    async function setCaseGroups() {
        const sourceFeatures = map.querySourceFeatures('caseWithGPS', {
            sourceLayer: 'clusters',
            filter: ['==', 'cluster', true],
        });
        const clusterSource = map.getSource('caseWithGPS');
        let caseGroups = {};
        let failedClustersCount = 0;
        processedCluster = {}

        for (const cluster of sourceFeatures) {
            const clusterId = cluster.properties.cluster_id;
            if (processedCluster[clusterId]) {
                continue;
            } else {
                processedCluster[clusterId] = true;
            }

            const pointCount = cluster.properties.point_count;

            try {
                const casePoints = await getClusterLeavesAsync(clusterSource, clusterId, pointCount);
                const groupUUID = uuidv4();
                for (const casePoint of casePoints) {
                    const caseId = casePoint.properties.id;
                    caseGroups[caseId] = {
                        groupId: groupUUID,
                        groupCoordinates: {
                            lng: cluster.geometry.coordinates[0],
                            lat: cluster.geometry.coordinates[1],
                        },
                    };
                }
            } catch (error) {
                failedClustersCount += 1;
            }
        }
        if (failedClustersCount > 0) {
            const message = _.template(gettext("Something went wrong processing <%- failedClusters %> groups. These groups will not be exported."))({
                failedClusters: failedClustersCount,
            });
            alertUser.alert_user(message, 'danger');
        }

        exportModelInstance.loadCaseGroups(caseGroups);
        collapseGroupsOnMap();
    }

    function clearCaseGroups() {
        setMapLayersVisibility(MAPBOX_LAYER_VISIBILITY.Visible);
        mapMarkers.forEach((marker) => marker.remove());
        mapMarkers = [];
        exportModelInstance.clearCaseGroups();
    }

    function groupLockModel() {
        'use strict';
        var self = {};

        self.groupsLocked = ko.observable(false);

        self.toggleGroupLock = function () {
            self.groupsLocked(!self.groupsLocked());
            if (self.groupsLocked()) {
                map.scrollZoom.disable();
                setCaseGroups();
            } else {
                map.scrollZoom.enable();
                clearCaseGroups();
            }
        };
        return self;
    }

    $(function () {
        let caseModels = [];
        exportModelInstance = new exportModel();

        // Parses a case row (which is an array of column values) to an object, using caseRowOrder as the order of the columns
        function parseCaseItem(caseItem, caseRowOrder) {
            let caseObj = {};
            for (const propKey in caseRowOrder) {
                const propIndex = caseRowOrder[propKey];
                caseObj[propKey] = caseItem[propIndex];
            }
            return caseObj;
        }

        function loadCases(rawCaseData) {
            caseModels = [];
            const caseRowOrder = initialPageData.get('case_row_order');
            for (const caseItem of rawCaseData) {
                const caseObj = parseCaseItem(caseItem, caseRowOrder);
                const caseModelInstance = new caseModel(caseObj.case_id, caseObj.gps_point, caseObj.link);
                caseModels.push(caseModelInstance);
            }
            exportModelInstance.casesToExport(caseModels);
        }

        $(document).ajaxComplete(function (event, xhr, settings) {
            const isAfterReportLoad = settings.url.includes('geospatial/async/case_grouping_map/');
            if (isAfterReportLoad) {
                $("#export-controls").koApplyBindings(exportModelInstance);
                $("#lock-groups-controls").koApplyBindings(new groupLockModel());
                map = initMap();
                $("#clusterStats").koApplyBindings(clusterStatsInstance);
                polygonFilterInstance = new polygonFilterModel();
                polygonFilterInstance.loadPolygons(initialPageData.get('saved_polygons'));
                $("#polygon-filters").koApplyBindings(polygonFilterInstance);

                return;
            }

            const isAfterDataLoad = settings.url.includes('geospatial/json/case_grouping_map/');
            if (!isAfterDataLoad) {
                return;
            }

            // Hide the datatable rows but not the pagination bar
            $('.dataTables_scroll').hide();

            const caseData = xhr.responseJSON.aaData;
            if (caseData.length) {
                loadCases(caseData);
                loadMapClusters(caseModels);
            }
        });
    });
});
