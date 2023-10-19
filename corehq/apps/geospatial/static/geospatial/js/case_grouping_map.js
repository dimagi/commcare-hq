hqDefine("geospatial/js/case_grouping_map",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    const MAP_CONTAINER_ID = 'case-grouping-map';
    let map;
    const clusterStatsInstance = new clusterStatsModel();

    function caseModel(caseId, coordiantes, caseLink) {
        'use strict';
        var self = {};
        self.caseId = caseId;
        self.coordinates = coordiantes;
        self.caseLink = caseLink;

        // TODO: Group ID needs to be set
        self.groupId = null;

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
                const coordinates = (caseItem.coordinates) ? `${caseItem.coordinates.lng} ${caseItem.coordinates.lat}` : "";
                return {
                    'groupId': caseItem.groupId,
                    'caseId': caseItem.caseId,
                    'coordinates': coordinates,
                };
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

        return self;
    }

    function getTodayDate() {
        const todayDate = new Date();
        return todayDate.toLocaleDateString();
    }

    function initMap() {
        'use strict';

        mapboxgl.accessToken = initialPageData.get('mapbox_access_token');
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

        return mapboxInstance;
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
                    }
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

    $(function () {
        let caseModels = [];
        const exportModelInstance = new exportModel();

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
                map = initMap();
                $("#clusterStats").koApplyBindings(clusterStatsInstance);
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