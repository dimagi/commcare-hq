hqDefine("geospatial/js/gps_capture",[
    "jquery",
    "knockout",
    'underscore',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/bootstrap3/components.ko", // for pagination
], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';
    const MAP_CONTAINER_ID = "geospatial-map";
    let map;

        var initMap = function () {
        'use strict';

        mapboxgl.accessToken = initialPageData.get('mapbox_access_token');  // eslint-disable-line no-undef

        let centerCoordinates = [2.43333330, 9.750]; // should be domain specific

        map = new mapboxgl.Map({  // eslint-disable-line no-undef
            container: MAP_CONTAINER_ID, // container ID
            style: 'mapbox://styles/mapbox/streets-v12', // style URL
            center: centerCoordinates, // starting position [lng, lat]
            zoom: 6,
            attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                         ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        });

        // adds mapbox street layers
        // full list https://studio.mapbox.com/tilesets/mapbox.mapbox-streets-v8
        map.on('load', () => {
            map.addSource('mapbox-streets', {
                type: 'vector',
                url: 'mapbox://mapbox.mapbox-streets-v8'
            });
            // works
            map.addLayer({
                id: 'admin',
                source: 'mapbox-streets',
                'source-layer': 'admin',
                type: 'line',
                paint: {
                    'line-color': '#800080' // purple
                }
            })
            // does not show up on the map; minzoom 9
//            map.addLayer({
//                id: 'aeroway',
//                source: 'mapbox-streets',
//                'source-layer': 'aeroway',
//                type: 'line',
//                paint: {
//                    'line-color': '#023020' // dark green
//                }
//            })
            // does not seem to be working; min zoom 8
//            map.addLayer({
//                id: 'airport_label',
//                source: 'mapbox-streets',
//                'source-layer': 'airport_label',
//                "type": "circle",
//                "paint": {
//                    "circle-radius": 3,
//                    "circle-color": "rgba(238,78,139, 0.4)",
//                    "circle-stroke-color": "rgba(238,78,139, 1)",
//                    "circle-stroke-width": 1
//                }
//            })
              // not working; min zoom is 13
//              map.addLayer({
//                id: 'mapbox-building',
//                source: 'mapbox-streets',
//                'source-layer': 'building',
//                type: 'fill',
//                "paint": {
//                    "fill-color": "rgba(66,100,251, 0.3)",
//                    "fill-outline-color": "rgba(66,100,251, 1)"
//                }
//              })

            /* crashes, minzoom 13
            map.addLayer({
                id: 'structure',
                type: 'fill',
                paint: {
                    "fill-color": "rgba(66,100,251, 0.3)",
                    "fill-outline-color": "rgba(66,100,251, 1)"
                },
                source: {
                    type: 'vector',
                    url: 'mapbox://mapbox.mapbox-streets-v8'
                },
                'source-layer': 'structure'
            });
            */
            // works fine; min zoom: 3
            map.addLayer({
                id: 'road',
                source: 'mapbox-streets',
                'source-layer': 'road',
                type: 'line',
                paint: {
                    'line-color': '#023020' // dark green
                }
            })
        });
        return map;
    };

    $(function () {
        initMap();
    });
});
