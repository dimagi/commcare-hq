hqDefine("geospatial/js/map", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "https://api.mapbox.com/mapbox-gl-js/v2.14.1/mapbox-gl.js",
    "https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-draw/v1.4.0/mapbox-gl-draw.js",
    "https://unpkg.com/@turf/turf@6/turf.min.js"
], function (
    $,
    initialPageData,
    mapboxgl,
    mapboxDraw,
    turf
) {
    $(function () {
        'use strict';
        mapboxgl.accessToken = initialPageData.get('mapbox_access_token');
        let centerCoordinates = [-91.874, 42.76]; // should be domain specific
        const map = new mapboxgl.Map({
            container: 'geospatial-map', // container ID
            style: 'mapbox://styles/mapbox/streets-v12', // style URL
            center: centerCoordinates, // starting position [lng, lat]
            zoom: 12 // starting zoom
        });

        const draw = new mapboxDraw({
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
            const answer = document.getElementById('calculated-area');
            if (data.features.length > 0) {
                const area = turf.area(data);
                // Restrict the area to 2 decimal points.
                const rounded_area = Math.round(area * 100) / 100;
                answer.innerHTML = `<p><strong>${rounded_area}</strong></p><p>square meters</p>`;
            } else {
                answer.innerHTML = '';
                if (e.type !== 'draw.delete') {
                    alert('Click the map to draw a polygon.');
                }
            }
        }

        // We should consider refactoring and splitting the below out to a new JS file
        let clickedMarker;

        function addCaseMarkersToMap(cases) {
            const markerColor = "#00FF00";
            cases.forEach(element => {
                addMarker(element.coordinates, markerColor);
            });
        };

        function addMarker(coordinates, color) {
            const marker = new mapboxgl.Marker({color: color, draggable: false});
            marker.setLngLat(coordinates);
            marker.addTo(map);
        }

        function moveMarkerToClickedCoordinate(coordinates) {
            if (clickedMarker != null) {
                clickedMarker.remove();
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
            // showCreateCasePopup(coordinates);
            // moveMarkerToClickedCoordinate(coordinates);
        });
    });
});
