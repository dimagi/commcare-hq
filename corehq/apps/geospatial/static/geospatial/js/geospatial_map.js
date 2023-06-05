hqDefine("geospatial/js/geospatial_map", [
    "jquery",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    initialPageData,
) {
    $(function () {
        const defaultMarkerColor = "#808080"; // Gray
        const selectedMarkerColor = "#00FF00"; // Green
        var map;
        var cases = [];
        var userFilteredCases = [];

        var loadMapBox = function (centerCoordinates) {
            'use strict';

            var self = {};
            let clickedMarker;
            mapboxgl.accessToken = initialPageData.get('mapbox_access_token');

            if (!centerCoordinates) {
                centerCoordinates = [-91.874, 42.76]; // should be domain specific
            }

            const map = new mapboxgl.Map({
                container: 'geospatial-map', // container ID
                style: 'mapbox://styles/mapbox/streets-v12', // style URL
                center: centerCoordinates, // starting position [lng, lat]
                zoom: 12,
                attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                             ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            });

            const draw = new MapboxDraw({
                // API: https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md
                displayControlsDefault: false,
                boxSelect: true, // enables box selection
                controls: {
                    polygon: true,
                    trash: true
                },
            });

            map.addControl(draw);

            map.on("draw.update", function(e) {
                var selectedFeatures = e.features;

                // Check if any features are selected
                if (!selectedFeatures.length) {
                    return;
                }
                var selectedFeature = selectedFeatures[0];

                if (selectedFeature.geometry.type == 'Polygon') {
                    filterCasesInPolygon(selectedFeature);
                }
            });

            map.on('draw.selectionchange', function(e) {
                // See https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md#drawselectionchange
                var selectedFeatures = e.features;
                if (!selectedFeatures.length) {
                    return;
                }
                // Check if any features are selected
                var selectedFeature = selectedFeatures[0];
                // Update this logic if we need to support case filtering by selecting multiple polygons

                if (selectedFeature.geometry.type == 'Polygon') {
                    // Now that we know we selected a polygon, we need to check which markers are inside
                    filterCasesInPolygon(selectedFeature);
                }
            });

            function getCoordinates(event) {
                return event.lngLat;
            };

            function changeCaseMarkerColor(selectedCase, newColor) {
                let marker = selectedCase.marker;
                let element = marker.getElement();
                let svg = element.getElementsByTagName("svg")[0];
                let path = svg.getElementsByTagName("path")[0];
                path.setAttribute("fill", newColor);
            };

            function filterCasesInPolygon(polygonFeature) {
                userFilteredCases = [];
                cases.filter(function (currCase) {
                    var coordinates = [currCase.coordinates.lng, currCase.coordinates.lat];
                    var point = turf.point(coordinates);
                    var caseIsInsidePolygon = turf.booleanPointInPolygon(point, polygonFeature.geometry);
                    if (caseIsInsidePolygon) {
                        userFilteredCases.push(currCase);
                        changeCaseMarkerColor(currCase, selectedMarkerColor);
                    } else {
                        changeCaseMarkerColor(currCase, defaultMarkerColor)
                    }
                });
            }

            // We should consider refactoring and splitting the below out to a new JS file
            function moveMarkerToClickedCoordinate(coordinates) {
                if (clickedMarker != null) {
                    clickedMarker.remove();
                }
                if (draw.getMode() === 'draw_polygon') {
                    // It's weird moving the marker around with the ploygon
                    return;
                }
                clickedMarker = new mapboxgl.Marker({color: "FF0000", draggable: true});
                clickedMarker.setLngLat(coordinates);
                clickedMarker.addTo(map);
            }

            self.getMapboxDrawInstance = function() {
                return draw;
            }

            self.getMapboxInstance = function() {
                return map;
            }

            self.clearMap = function() {
                // Clear filtered cases
                userFilteredCases = [];
                // Remove markers
                cases.forEach(currCase => {
                    if (currCase.marker) {
                        currCase.marker.remove();
                    }
                })
                cases = [];
            }

            self.addCaseMarkersToMap = function () {
                cases.forEach(element => {
                    let coordinates = element.coordinates;
                    if (coordinates && coordinates.lat && coordinates.lng) {
                        self.addMarker(element, defaultMarkerColor);
                    }
                });
            };

            self.addMarker = function (currCase, color) {
                let coordinates = currCase.coordinates;
                // Create the marker
                const marker = new mapboxgl.Marker({ color: color, draggable: false });
                marker.setLngLat(coordinates);

                // Add the marker to the map
                marker.addTo(map);
                // We need to keep track of current markers

                currCase.marker = marker;
            };

            // Handle click events here
            map.on('click', (event) => {
                let coordinates = getCoordinates(event);
            });
            return self;
        };

        var exportGeoJson = function(drawInstance) {
            // Credit to https://gist.github.com/danswick/36796153bd86ce982a59043cbe0ac8f7
            var exportButton = $("#btnExport");
            var data = drawInstance.getAll();

            if (data.features.length) {
                // Stringify the GeoJson
                var convertedData = 'text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data));

                // Create export
                exportButton.attr('href', 'data:' + convertedData);
                exportButton.attr('download','data.geojson');
            }
        };

        $(document).ajaxComplete(function () {
            // This fires everytime an ajax request is completed
            var mapDiv = $('#geospatial-map');
            var $data = $(".map-data");
            var exportButton = $("#btnExport");

            if (mapDiv.length && !map) {
                map = loadMapBox();
            }

            exportButton.click(function(e) {
                if (map) {
                    exportGeoJson(map.getMapboxDrawInstance());
                }
            });

            if ($data.length && map) {
                var caseData = $data.data("context");
                map.clearMap();
                cases = caseData.cases
                map.addCaseMarkersToMap();
            }
        });
    });
});
