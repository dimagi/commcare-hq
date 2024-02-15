hqDefine("geospatial/js/case_grouping_map",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/alert_user',
    'geospatial/js/models',
    'geospatial/js/utils'
], function (
    $,
    ko,
    _,
    initialPageData,
    alertUser,
    models,
    utils
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
    const clusterStatsInstance = new clusterStatsModel();
    let exportModelInstance;
    let groupLockModelInstance = new groupLockModel();
    let caseGroupsInstance = new caseGroupSelectModel();
    let mapMarkers = [];

    let mapModel;
    let polygonFilterInstance;
    let currentPage = 1;

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
            let groupNameByID = _.object(_.map(caseGroupsInstance.generatedGroups, function(group) {
                return [group.groupId, group.name]
            }));

            // Write headers first
            let headers = [
                gettext('Group ID'),
                gettext('Group Name'),
                gettext('Group Center Coordinates'),
                gettext('Case Name'),
                gettext('Case Owner Name'),
                gettext('Case Coordinates'),
                gettext('Case ID'),
            ]
            csvStr = (headers).join(",");
            csvStr += "\n";

            _.forEach(casesToExport, function (caseToExport) {
                csvStr += [
                    caseToExport.groupId,
                    groupNameByID[caseToExport.groupId],
                    caseToExport.groupCenterCoordinates,
                    caseToExport.caseName,
                    caseToExport.owner_name,
                    caseToExport.coordinates,
                    caseToExport.caseId,
                ].join(",");
                csvStr += "\n";
            });

            // Download CSV file
            const hiddenElement = document.createElement('a');
            hiddenElement.href = 'data:text/csv;charset=utf-8,' + encodeURI(csvStr);
            hiddenElement.target = '_blank';
            hiddenElement.download = `Grouped Cases (${utils.getTodayDate()}).csv`;
            hiddenElement.click();
            hiddenElement.remove();
        };

        self.addGroupDataToCases = function(caseGroups, groupsData, assignDefaultGroup) {
            const defaultGroup = groupsData.find((group) => {return group.groupId === DEFAULT_GROUP_ID});
            self.casesToExport().forEach(caseItem => {
                const groupId = caseGroups[caseItem.itemId];
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
            var item = self.casesToExport().find((caseItem) => {return caseItem.itemId == itemId});
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

        self.groupsReady = function() {
            return groupLockModelInstance.groupsLocked();
        }

        return self;
    }

    function updateClusterStats() {
        const sourceFeatures = mapModel.mapInstance.querySourceFeatures('caseWithGPS', {
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
            const coordinates = caseWithGPS.itemData.coordinates;
            if (coordinates && coordinates.lat && coordinates.lng) {
                caseLocationsGeoJson["features"].push(
                    {
                        "type": "feature",
                        "properties": {
                            "id": caseWithGPS.itemId,
                        },
                        "geometry": {
                            "type": "Point",
                            "coordinates": [coordinates.lng, coordinates.lat],
                        },
                    }
                );
            }
        });

        if (mapModel.mapInstance.getSource('caseWithGPS')) {
            mapModel.mapInstance.getSource('caseWithGPS').setData(caseLocationsGeoJson);
        } else {
            mapModel.mapInstance.on('load', () => {
                mapModel.mapInstance.getSource('caseWithGPS').setData(caseLocationsGeoJson);
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
        mapModel.mapInstance.setLayoutProperty('clusters', 'visibility', visibility);
        mapModel.mapInstance.setLayoutProperty('cluster-count', 'visibility', visibility);
        mapModel.mapInstance.setLayoutProperty('unclustered-point', 'visibility', visibility);
    }

    function mapMarkerModel(itemId, itemData, marker, markerColors) {
        'use strict';
        var self = {};
        self.title = gettext("Select group");
        self.itemId = itemId;
        self.itemData = itemData;
        self.marker = marker;
        self.selectCssId = "select" + itemId;
        self.isSelected = ko.observable(false);
        self.markerColors = markerColors;

        self.groupsOptions = ko.observable(caseGroupsInstance.generatedGroups);
        self.selectedGroup = ko.observable(itemData.groupId);

        self.updateGroup = ko.computed(function () {
            if (!self.itemId) {
                return;
            }
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

        let groupColorByID = _.object(_.map(caseGroupsInstance.generatedGroups, function(group) {
            return [group.groupId, group.color]
        }));

        exportModelInstance.casesToExport().forEach(function (caseItem) {
            const coordinates = caseItem.itemData.coordinates;
            if (!coordinates) {
                return;
            }
            const caseGroupID = caseItem.groupId;
            if (caseGroupsInstance.groupIDInVisibleGroupIds(caseGroupID)) {
                color = groupColorByID[caseGroupID];
                const marker = new mapboxgl.Marker({ color: color, draggable: false });  // eslint-disable-line no-undef
                marker.setLngLat([coordinates.lng, coordinates.lat]);

                // Add the marker to the map
                marker.addTo(mapModel.mapInstance);
                mapMarkers.push(marker);

                const popupDiv = document.createElement("div");
                const popup = utils.createMapPopup(coordinates, popupDiv, marker.togglePopup, marker.togglePopup);

                marker.setPopup(popup);
                const colors = {default: color, selected: color};

                const mapMarkerInstance = new mapMarkerModel(caseItem.itemId, caseItem, marker, colors);
                $(popupDiv).koApplyBindings(mapMarkerInstance);
            }
        });
    }

    function caseGroupSelectModel() {
        'use strict';
        var self = {};

        self.groupsByCase;
        // generatedGroups and caseGroupsForTable contains the same data, but there's weird knockoutjs behaviour
        // if we're making generatedGroups an observable. caseGroupsForTable is populated by setCaseGroupsForTable
        self.generatedGroups = [];
        self.caseGroupsForTable = ko.observableArray([]);
        self.visibleGroupIDs = ko.observableArray([]);
        self.casePerGroup = {};

        self.groupIDInVisibleGroupIds = function(groupID) {
            return self.visibleGroupIDs().indexOf(groupID) !== -1;
        };

        self.getGroupByID = function(groupID) {
            return self.generatedGroups.find((group) => group.groupId === groupID);
        };

        self.updateCaseGroup = function(itemId, newGroupId) {
            self.groupsByCase[itemId] = newGroupId;
        };

        self.loadCaseGroups = function(caseGroups, groups) {
            self.groupsByCase = caseGroups;
            self.generatedGroups = groups;

            self.showAllGroups();
        };

        self.clear = function() {
            self.generatedGroups = [];
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
                        let caseCoordinates = caseItem.itemData.coordinates;
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
            if (!self.groupsByCase) {
                return;
            }

            let filteredCaseGroups = {};
            for (const caseID in self.groupsByCase) {
                if (self.groupIDInVisibleGroupIds(self.groupsByCase[caseID])) {
                    filteredCaseGroups[caseID] = self.groupsByCase[caseID];
                }
            }
            exportModelInstance.addGroupDataToCases(filteredCaseGroups, self.generatedGroups);
            revealGroupsOnMap();
        };

        self.showAllGroups = function() {
            if (!self.groupsByCase) {
                return;
            }
            self.visibleGroupIDs(_.map(self.generatedGroups, function(group) {return group.groupId}));
            revealGroupsOnMap();
            self.setCaseGroupsForTable();
        };

        self.setCaseGroupsForTable = function() {
            self.caseGroupsForTable(self.generatedGroups);
        }

        self.groupsReady = function() {
            return groupLockModelInstance.groupsLocked() && self.caseGroupsForTable().length;
        };

        return self;
    }

    async function setCaseGroups() {
        const sourceFeatures = mapModel.mapInstance.querySourceFeatures('caseWithGPS', {
            sourceLayer: 'clusters',
            filter: ['==', 'cluster', true],
        });
        const clusterSource = mapModel.mapInstance.getSource('caseWithGPS');
        let caseGroups = {};
        let failedClustersCount = 0;
        processedCluster = {};

        var groupCount = 1;
        var groups = [DEFAULT_GROUP];

        for (const cluster of sourceFeatures) {
            const clusterId = cluster.properties.cluster_id;
            if (processedCluster[clusterId] === undefined) {
                processedCluster[clusterId] = true;
            }
            else {
                continue;
            }

            const pointCount = cluster.properties.point_count;

            try {
                const casePoints = await getClusterLeavesAsync(clusterSource, clusterId, pointCount);
                const groupUUID =  utils.uuidv4();

                if (casePoints.length) {
                    groupName = _.template(gettext("Group <%- pageNumber %>-<%- groupCount %>"))({
                        groupCount: groupCount,
                        pageNumber: currentPage,
                    });
                    groupCount += 1;

                    groups.push({
                        name: groupName,
                        groupId: groupUUID,
                        color: utils.getRandomRGBColor(),
                        coordinates: {
                            lng: cluster.geometry.coordinates[0],
                            lat: cluster.geometry.coordinates[1],
                        }
                    });
                    for (const casePoint of casePoints) {
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
        exportModelInstance.clearCaseGroups();
        caseGroupsInstance.clear();
    }

    function groupLockModel() {
        'use strict';
        var self = {};

        self.groupsLocked = ko.observable(false);

        self.toggleGroupLock = function () {
            // reset the warning banner
            self.groupsLocked(!self.groupsLocked());
            if (self.groupsLocked()) {
                mapModel.mapInstance.scrollZoom.disable();
                setCaseGroups();
            } else {
                mapModel.mapInstance.scrollZoom.enable();
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
                const caseModelInstance = new models.GroupedCaseMapItem(caseObj.case_id, caseObj, caseObj.link);
                caseModels.push(caseModelInstance);
            }
            mapModel.caseMapItems(caseModels);
            exportModelInstance.casesToExport(caseModels);

            mapModel.fitMapBounds(caseModels);
        }

        function initMap() {
            mapModel = new models.Map(true);
            mapModel.initMap(MAP_CONTAINER_ID);

            mapModel.mapInstance.on('moveend', updateClusterStats);
            mapModel.mapInstance.on("draw.update", (e) => {
                polygonFilterInstance.addPolygonsToFilterList(e.features);
            });
            mapModel.mapInstance.on('draw.delete', function (e) {
                polygonFilterInstance.removePolygonsFromFilterList(e.features);
            });
            mapModel.mapInstance.on('draw.create', function (e) {
                polygonFilterInstance.addPolygonsToFilterList(e.features);
            });
        }

        $(document).ajaxComplete(function (event, xhr, settings) {
            const isAfterReportLoad = settings.url.includes('geospatial/async/case_grouping_map/');
            if (isAfterReportLoad) {
                $("#export-controls").koApplyBindings(exportModelInstance);
                $("#lock-groups-controls").koApplyBindings(groupLockModelInstance);
                initMap();
                $("#clusterStats").koApplyBindings(clusterStatsInstance);
                polygonFilterInstance = new models.PolygonFilter(mapModel, true, false);
                polygonFilterInstance.loadPolygons(initialPageData.get('saved_polygons'));
                $("#polygon-filters").koApplyBindings(polygonFilterInstance);

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
            currentPage = xhr.responseJSON.sEcho;
            if (caseData.length) {
                loadCases(caseData);
                loadMapClusters(caseModels);
            }
        });
    });
});
