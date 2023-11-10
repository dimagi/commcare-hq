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

    const DEFAULT_MARKER_OPACITY = 1.0;
    const OBSCURING_OPACITY = 0.2;
    const DEFAULT_GROUP_ID = "unassigned-group-id";
    const DEFAULT_GROUP = {
        groupId: DEFAULT_GROUP_ID,
        name: gettext("No group"),
        color: `rgba(128,128,128,${OBSCURING_OPACITY})`,
    }

    const MAP_CONTAINER_ID = 'case-grouping-map';
    let map;
    const clusterStatsInstance = new clusterStatsModel();
    let exportModelInstance;
    let groupLockModelInstance = new groupLockModel();
    let caseGroupsInstance = new caseGroupSelectModel();
    let mapMarkers = [];

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

            // Only cases with belonging to groups should be exported
            let exportableCases = self.casesToExport().filter(function(caseItem) {
                return caseItem.groupId !== DEFAULT_GROUP_ID;
            });

            if (!exportableCases.length) {
                // If no case belongs to a group, we export all cases
                exportableCases = self.casesToExport();
            }

            const casesToExport = _.map(exportableCases, function (caseItem) {
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

        self.addGroupDataToCases = function(caseGroups, groupsData, assignDefaultGroup) {
            const defaultGroup = groupsData[0];
            self.casesToExport().forEach(caseItem => {
                const groupId = caseGroups[caseItem.caseId];
                if (groupId !== undefined) {
                    const group = groupsData.find((group) => {return group.groupId === groupId});
                    self.setItemGroup(caseItem, groupId, group.coordinates);
                } else if (assignDefaultGroup) {
                    self.setItemGroup(caseItem, defaultGroup.groupId, {});
                }
            });
        }

        self.setItemGroup = function(item, groupId, groupCoordinates) {
            item.groupId = groupId;
            item.groupCoordinates = groupCoordinates;
        }

        self.updateCaseGroup = function(itemId, groupData) {
            var item = self.casesToExport().find((caseItem) => {return caseItem.caseId == itemId});
            self.setItemGroup(item, groupData.groupId, groupData.coordinates);
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
        mapboxInstance.on('moveend', updateClusterStats);

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

    function getRandomRGBColor() { // TODO: Ensure generated colors looks different!
        var r = Math.floor(Math.random() * 256); // Random value between 0 and 255 for red
        var g = Math.floor(Math.random() * 256); // Random value between 0 and 255 for green
        var b = Math.floor(Math.random() * 256); // Random value between 0 and 255 for blue

        return `rgba(${r},${g},${b},${DEFAULT_MARKER_OPACITY})`;
    }

    function mapMarkerModel(itemId, itemData, marker, markerColors) {
        'use strict';
        var self = {};
        self.itemId = itemId;
        self.itemData = itemData;
        self.marker = marker;
        self.selectCssId = "select" + itemId;
        self.isSelected = ko.observable(false);
        self.markerColors = markerColors;

        self.groupsOptions = ko.observable(caseGroupsInstance.allGroups);
        self.selectedGroup = ko.observable(itemData.groupId);

        self.updateGroup = ko.computed(function () {
            caseGroupsInstance.updateCaseGroup(self.itemId, self.selectedGroup());
            const newGroup = caseGroupsInstance.getGroupByID(self.selectedGroup());
            if (newGroup) {
                changeMarkerColor(self, newGroup.color);
                exportModelInstance.updateCaseGroup(self.itemId, newGroup);
            }
        });

        function changeMarkerColor(selectedCase, newColor) {
            let marker = selectedCase.marker;
            let element = marker.getElement();
            let svg = element.getElementsByTagName("svg")[0];
            let path = svg.getElementsByTagName("path")[0];
            path.setAttribute("fill", newColor);
        }

        return self;
    }

    function revealGroupsOnMap() {
        setMapLayersVisibility(MAPBOX_LAYER_VISIBILITY.None);
        mapMarkers.forEach((marker) => marker.remove());
        mapMarkers = [];
        exportModelInstance.casesToExport().forEach(function (caseItem) {
            if (!caseItem.coordinates) {
                return;
            }
            const caseGroupID = caseItem.groupId;
            if (caseGroupsInstance.groupIDInVisibleGroupIds(caseGroupID)) {
                let caseGroup = caseGroupsInstance.getGroupByID(caseGroupID);
                color = caseGroup.color;
                const marker = new mapboxgl.Marker({ color: color, draggable: false });  // eslint-disable-line no-undef

                const coordinates = [caseItem.coordinates.lng, caseItem.coordinates.lat];
                marker.setLngLat(coordinates);

                // Add the marker to the map
                marker.addTo(map);
                mapMarkers.push(marker);

                let popupDiv = document.createElement("div");
                popupDiv.setAttribute("data-bind", "template: 'select-case'");

                let popup = new mapboxgl.Popup({ offset: 25, anchor: "bottom" })  // eslint-disable-line no-undef
                    .setLngLat(coordinates)
                    .setDOMContent(popupDiv);

                marker.setPopup(popup);

                const markerDiv = marker.getElement();
                // Show popup on hover
                markerDiv.addEventListener('mouseenter', () => marker.togglePopup());

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
                const colors = {default: color, selected: color};

                const mapMarkerInstance = new mapMarkerModel(caseItem.caseId, caseItem, marker, colors);
                $(popupDiv).koApplyBindings(mapMarkerInstance);
            }
        });
    }

    function uuidv4() {
        // https://stackoverflow.com/questions/105034/how-do-i-create-a-guid-uuid/2117523#2117523
        return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
            (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16),
        );
    }

    function caseGroupSelectModel() {
        'use strict';
        var self = {};

        self.allCaseGroups;
        // allGroups and caseGroupsForTable contains the same data, but there's weird knockoutjs behaviour
        // if we're making allGroups an observable. caseGroupsForTable is populated by setCaseGroupsForTable
        self.allGroups = [];
        self.caseGroupsForTable = ko.observableArray([]);
        self.visibleGroupIDs = ko.observableArray([]);
        self.casePerGroup = {};

        self.groupIDInVisibleGroupIds = function(groupID) {
            return self.visibleGroupIDs().indexOf(groupID) !== -1;
        };

        self.getGroupByID = function(groupID) {
            return self.allGroups.find((group) => group.groupId === groupID);
        };

        self.updateCaseGroup = function(itemId, newGroupId) {
            self.allCaseGroups[itemId] = newGroupId;
        };

        self.loadCaseGroups = function(caseGroups, groups) {
            self.allCaseGroups = caseGroups;
            self.allGroups = groups;

            self.showAllGroups();
        };

        self.clear = function() {
            self.allGroups = [];
            self.caseGroupsForTable([]);
            self.visibleGroupIDs([]);
        };

        self.restoreMarkerOpacity = function() {
            mapMarkers.forEach(function(marker) {
                setMarkerOpacity(marker, DEFAULT_MARKER_OPACITY);
            });
        };

        self.highlightGroup = function(group) {
            exportModelInstance.casesToExport().forEach(caseItem => {
                    let caseIsInGroup = caseItem.groupId === group.groupId;
                    let opacity = DEFAULT_MARKER_OPACITY
                    if (!caseIsInGroup) {
                        opacity = OBSCURING_OPACITY;
                    }
                    let marker = mapMarkers.find((marker) => {
                        let markerCoordinates = marker.getLngLat();
                        let caseCoordinates = caseItem.coordinates;
                        let latEqual = markerCoordinates.lat === caseCoordinates.lat;
                        let lonEqual = markerCoordinates.lng === caseCoordinates.lng;
                        return latEqual && lonEqual;
                    });
                    if (marker) {
                        setMarkerOpacity(marker, opacity);
                    }
            });
        };

        function setMarkerOpacity(marker, opacity) {
            let element = marker.getElement();
            element.style.opacity = opacity;
        };

        self.showSelectedGroups = function() {
            if (!self.allCaseGroups) {
                return;
            }

            let filteredCaseGroups = {};
            for (const caseID in self.allCaseGroups) {
                if (self.groupIDInVisibleGroupIds(self.allCaseGroups[caseID])) {
                    filteredCaseGroups[caseID] = self.allCaseGroups[caseID];
                }
            }
            exportModelInstance.addGroupDataToCases(filteredCaseGroups, self.allGroups);
            revealGroupsOnMap();
        };

        self.showAllGroups = function() {
            if (!self.allCaseGroups) {
                return;
            }
            self.visibleGroupIDs(_.map(self.allGroups, function(group) {return group.groupId}));
            revealGroupsOnMap();
            self.setCaseGroupsForTable();
        };

        self.setCaseGroupsForTable = function() {
            self.caseGroupsForTable(self.allGroups);
        }

        return self;
    }

    async function setCaseGroups() {
        const sourceFeatures = map.querySourceFeatures('caseWithGPS', {
            sourceLayer: 'clusters',
            filter: ['==', 'cluster', true],
        });
        const clusterSource = map.getSource('caseWithGPS');
        let caseGroups = {};  // e.g. {<case_id>: <group_id>}
        let failedClustersCount = 0;
        processedCluster = {};

        var groupCount = 1;
        var groups = [DEFAULT_GROUP];

        for (const cluster of sourceFeatures) {
            const clusterId = cluster.properties.cluster_id;
            if (processedCluster[clusterId] == undefined) {
                processedCluster[clusterId] = true;
            }
            else {
                continue;
            }

            const pointCount = cluster.properties.point_count;

            try {
                const casePoints = await getClusterLeavesAsync(clusterSource, clusterId, pointCount);
                const groupUUID = uuidv4();

                if (casePoints.length > 0) {
                    groupName = _.template(gettext("Group <%- groupCount %>"))({
                        groupCount: groupCount,
                    });
                    groupCount += 1;

                    groups.push({
                        name: groupName,
                        groupId: groupUUID,
                        color: getRandomRGBColor(),
                        coordinates: {
                            lng: cluster.geometry.coordinates[0],
                            lat: cluster.geometry.coordinates[1],
                        }
                    });
                    for (const casePoint of casePoints) {
                        console.log("Hitting case and adding to group");
                        const caseId = casePoint.properties.id;
                        caseGroups[caseId] = groupUUID;
                    }
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
        exportModelInstance.addGroupDataToCases(caseGroups, groups, true);
        caseGroupsInstance.loadCaseGroups(caseGroups, groups);
    }

    function clearCaseGroups() {
        setMapLayersVisibility(MAPBOX_LAYER_VISIBILITY.Visible);
        mapMarkers.forEach((marker) => marker.remove());
        mapMarkers = [];
        caseGroupsInstance.clear();
        exportModelInstance.clearCaseGroups();
    }

    function groupLockModel() {
        'use strict';
        var self = {};

        self.groupsLocked = ko.observable(false);

        self.toggleGroupLock = function () {
            // reset the warning banner
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
                $("#lock-groups-controls").koApplyBindings(groupLockModelInstance);
                map = initMap();
                $("#clusterStats").koApplyBindings(clusterStatsInstance);
                $("#caseGroupSelect").koApplyBindings(caseGroupsInstance);
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
