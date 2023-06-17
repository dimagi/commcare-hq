hqDefine("geospatial/js/geospatial_map", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "knockout",
], function (
    $,
    initialPageData,
    ko
) {
    $(function () {
        const defaultMarkerColor = "#808080"; // Gray
        const selectedMarkerColor = "#00FF00"; // Green
        var map;
        var cases = [];
        var userFilteredCases = [];
        var saveGeoJSONUrl = initialPageData.reverse('geo_polygon');

        function filterCasesInPolygon(polygonFeature) {
            userFilteredCases = [];
            cases.filter(function (currCase) {
                if (currCase.coordinates) {
                    var coordinates = [currCase.coordinates.lng, currCase.coordinates.lat];
                    var point = turf.point(coordinates);
                    var caseIsInsidePolygon = turf.booleanPointInPolygon(point, polygonFeature.geometry);
                    if (caseIsInsidePolygon) {
                        userFilteredCases.push(currCase);
                        changeCaseMarkerColor(currCase, selectedMarkerColor);
                    } else {
                        changeCaseMarkerColor(currCase, defaultMarkerColor)
                    }
                }
            });
        }

        function changeCaseMarkerColor(selectedCase, newColor) {
            let marker = selectedCase.marker;
            let element = marker.getElement();
            let svg = element.getElementsByTagName("svg")[0];
            let path = svg.getElementsByTagName("path")[0];
            path.setAttribute("fill", newColor);
        };

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

        var exportGeoJson = function(drawInstance, mapControlsModelInstance) {
            // Credit to https://gist.github.com/danswick/36796153bd86ce982a59043cbe0ac8f7
            // I could not get this to work using knockout.js. It did set the attributes, but a download wasn't
            // triggered
            var exportButton = $("#btnExport");
            var data = drawInstance.getAll();

            if (data.features.length) {
                let name = window.prompt("Name of the Area");
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
                                geo_json: data
                            })
                        );
                        // redraw using mapControlsModelInstance
                        mapControlsModelInstance.selectedPolygon(ret.id);
                        alert('saved!');
                    }
                });
            }
        };

        function savedPolygon(polygon) {
            var self = {};
            self.text = polygon.name;
            self.id = polygon.id;
            self.geoJson = polygon.geo_json;
            return self;
        }

        var mapControlsModel = function () {
            'use strict';
            var self = {};
            var mapboxinstance = map.getMapboxInstance();
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
                var polygonObj = self.savedPolygons().find(
                    function (o) { return o.id == self.selectedPolygon(); }
                );
                // Clear existing polygon
                if (self.activePolygon()) {
                    mapboxinstance.removeLayer(self.activePolygon());
                    mapboxinstance.removeSource(self.activePolygon());
                }
                // Add selected polygon
                mapboxinstance.addSource(
                    String(polygonObj.id),
                    {'type': 'geojson', 'data':polygonObj.geoJson}
                );
                mapboxinstance.addLayer({
                    'id': String(polygonObj.id),
                    'type': 'fill',
                    'source': String(polygonObj.id),
                    'layout': {},
                    'paint': {
                        'fill-color': '#0080ff',
                        'fill-opacity': 0.5
                    }
                });
                polygonObj.geoJson.features.forEach(
                    filterCasesInPolygon
                );
                // Mark as active polygon
                self.activePolygon(self.selectedPolygon());
            });

            var mapHasPolygons = function() {
                var drawnFeatures = map.getMapboxDrawInstance().getAll().features;
                if (!drawnFeatures.length) {
                    return false;
                }
                return drawnFeatures.some(function(feature) {
                    return feature.geometry.type === "Polygon";
                })
            };

            mapboxinstance.on('draw.delete', function(e) {
                self.btnExportDisabled(!mapHasPolygons());
            });

            mapboxinstance.on('draw.create', function(e) {
                self.btnExportDisabled(!mapHasPolygons());
            });

            return self;
        }


        $(document).ajaxComplete(function (event, xhr, settings) {
            // This indicates that the report data is fetched
            if (!settings.url.includes('geospatial/async/case_management_map/')) {
                return;
            }
            var mapDiv = $('#geospatial-map');
            var $data = $(".map-data");
            var $exportButton = $("#btnExport");
            var $mapControlDiv = $("#mapControls");

            if (mapDiv.length && !map) {
                map = loadMapBox();
            }

            var mapControlsModelInstance = mapControlsModel();

            if ($data.length && map) {
                var caseData = $data.data("context");
                map.clearMap();
                cases = caseData.cases
                map.addCaseMarkersToMap();
            }

            if ($mapControlDiv.length) {
                $mapControlDiv.koApplyBindings(mapControlsModelInstance);
            }

            $exportButton.click(function(e) {
                if (map) {
                    exportGeoJson(map.getMapboxDrawInstance(), mapControlsModelInstance);
                }
            });
        });
    });
});
