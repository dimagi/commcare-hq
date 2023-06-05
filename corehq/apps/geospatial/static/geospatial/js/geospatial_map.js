hqDefine("geospatial/js/geospatial_map", [
    "jquery",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    initialPageData,
) {
    $(function () {
        var map;
        var cases = [];
        var userFilteredCases = [];

        var loadMapBox = function (centerCoordinates) {
            'use strict';

            var self = {};
            var markers = [];
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

            function getCoordinates(event) {
                return event.lngLat;
            };

            map.on("draw.update", function(e) {
                var selectedFeature = e.features[0];
                if (selectedFeature.geometry.type == 'Polygon') {
                    // Filter for selected cases when dragging a polygon
                    var polygon = selectedFeature.geometry;
                    filterCasesInPolygon(polygon);
                }
            });

            map.on('draw.selectionchange', function(e) {
                // See https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/API.md#drawselectionchange
                var selectedFeatures = e.features;

                // Check if any features are selected
                if (selectedFeatures.length > 0) {
                    var selectedFeature = selectedFeatures[0];
                    // Update this logic if we need to support case filtering by selecting multiple polygons

                    if (selectedFeature.geometry.type == 'Polygon') {
                        // Now that we know we selected a polygon, we need to check which markers are inside
                        var polygon = selectedFeature.geometry;
                        filterCasesInPolygon(polygon);
                    }
                }
            });

            function filterCasesInPolygon(polygonGeometry) {
                userFilteredCases = [];
                cases.filter(function (currCase) {
                    var coordinates = [currCase.coordinates.lng, currCase.coordinates.lat];
                    var point = turf.point(coordinates);
                    var caseIsInsidePolygon = turf.booleanPointInPolygon(point, polygonGeometry);
                    if (caseIsInsidePolygon) {
                        userFilteredCases.push(currCase)
                    };
                });
                console.log(userFilteredCases);
            }

            // We should consider refactoring and splitting the below out to a new JS file
            let clickedMarker;

            self.getMapboxInstance = function() {
                return map;
            }

            self.removeAllMarkers = function() {
                markers.forEach(marker => {
                    marker.remove();
                })
                markers = []
            }

            self.addCaseMarkersToMap = function () {
                const markerColor = "#00FF00";
                cases.forEach(element => {
                    let coordinates = element.coordinates;
                    if (coordinates && coordinates.lat && coordinates.lng) {
                        self.addMarker(coordinates, markerColor);
                    }
                });
            };

            self.addMarker = function (coordinates, color) {
                // Create the marker
                const marker = new mapboxgl.Marker({ color: color, draggable: false });
                marker.setLngLat(coordinates);

                // Add the marker to the map
                marker.addTo(map);
                // We need to keep track of current markers
                markers.push(marker);
            };

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

            // Handle click events here
            map.on('click', (event) => {
                let coordinates = getCoordinates(event);
            });
            return self;
        };


        $(document).ajaxComplete(function () {
            // This fires everytime an ajax request is completed
            var mapDiv = $('#geospatial-map');
            var $data = $(".map-data");

            if (mapDiv.length && !map) {
                map = loadMapBox();
            }

            if ($data.length && map) {
                var caseData = $data.data("context");
                map.removeAllMarkers();
                cases = caseData.cases
                map.addCaseMarkersToMap();
            }
        });
    });
});
