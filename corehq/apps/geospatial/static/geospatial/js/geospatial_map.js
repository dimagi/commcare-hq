hqDefine("geospatial/js/geospatial_map", [
    "jquery",
    "hqwebapp/js/initial_page_data",
], function (
    $,
    initialPageData,
) {
    $(function () {
        var loadMapBox = function (centerCoordinates) {
            'use strict';

            var self = {};
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

            map.on('draw.create', updateArea);
            map.on('draw.delete', updateArea);
            map.on('draw.update', updateArea);

            function getCoordinates(event) {
                return event.lngLat;
            };

            function updateArea(e) {
                const data = draw.getAll();
                const area = turf.area(data);
                // Restrict the area to 2 decimal points.
                const rounded_area = Math.round(area * 100) / 100;
            }

            // We should consider refactoring and splitting the below out to a new JS file
            let clickedMarker;

            self.getMapboxInstance = function() {
                return map;
            }
            self.addCaseMarkersToMap = function (cases) {
                const markerColor = "#00FF00";
                cases.forEach(element => {
                    let coordinates = element.coordinates;
                    if (coordinates && coordinates.lat && coordinates.lng) {
                        self.addMarker(coordinates, markerColor);
                    }
                });
            };

            self.addMarker = function (coordinates, color) {
                const marker = new mapboxgl.Marker({color: color, draggable: false});
                marker.setLngLat(coordinates);
                marker.addTo(map);
            }

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

            function showCreateCasePopup(coordinates) {
                new mapboxgl.Popup()
                .setLngLat(coordinates)
                .setHTML(coordinates + '<br/><button> Create Case at this point </button>')
                .addTo(map);
            }

            // Handle click events here
            map.on('click', (event) => {
                let coordinates = getCoordinates(event);
                moveMarkerToClickedCoordinate(coordinates);
            });
            return self;
        };

        var map;

        $(document).on('click', '#apply-filters', function() {
            if (map) {
                mapbox = map.getMapboxInstance();
                mapbox.remove();
                map = null;
            }
        })

        $(document).ajaxComplete(function () {
            var mapDiv = $('#geospatial-map');
            var $data = $(".map-data");

            if (mapDiv.length && !map) {
                map = loadMapBox();
            }

            if ($data.length && map) {
                var caseData = $data.data("context");
                map.addCaseMarkersToMap(caseData.cases)
            }
        });
    });
});
