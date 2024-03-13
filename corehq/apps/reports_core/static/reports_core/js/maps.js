/*globals hqDefine */
hqDefine('reports_core/js/maps', function () {
    var module = {},
        privates = {};

    // helpful article on migrating to new mapbox api and why to include tileSize=512 and zoomOffset=-1
    // https://docs.mapbox.com/help/troubleshooting/migrate-legacy-static-tiles-api/?/=blog&utm_source=mapbox-blog&utm_campaign=blog%7Cmapbox-blog%7Cdoc-migrate-static%7Cdeprecating-studio-classic-styles-d8892ac38cb4-20-03&utm_term=doc-migrate-static&utm_content=deprecating-studio-classic-styles-d8892ac38cb4
    var getTileLayer = function (layerId, accessToken) {
        return L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
            id: layerId,
            accessToken: accessToken,
            maxZoom: 17,
            tileSize: 512,
            zoomOffset: -1,
        });
    };

    var init_map = function (config, mapContainer) {
        if (!privates.hasOwnProperty('map')) {
            mapContainer.show();
            mapContainer.empty();
            var streets = getTileLayer('mapbox/streets-v11', config.mapboxAccessToken),
                satellite = getTileLayer('mapbox/satellite-streets-v11', config.mapboxAccessToken);

            privates.map = L.map(mapContainer[0], {
                trackResize: false,
                layers: [streets],
                // remove attribution control to duplicate "Leaflet" attribute
                attributionControl: false,
                zoomControl: false,
            }).setView([0, 0], 3);

            var baseMaps = {};
            baseMaps[gettext("Streets")] = streets;
            baseMaps[gettext("Satellite")] = satellite;

            privates.layerControl = L.control.layers(baseMaps);
            privates.layerControl.addTo(privates.map);

            new (hqImport("reports/js/maps_utils").ZoomToFitControl)().addTo(privates.map);
            // Add MapBox wordmark and correct attributes to map
            // See https://docs.mapbox.com/help/how-mapbox-works/attribution/
            new (hqImport("reports/js/maps_utils").MapBoxWordMark)().addTo(privates.map);
            // scale is now placed on the bottom right because it is easier to layout with the attributes than with the wordmark
            L.control.attribution({position: 'bottomright'}).addAttribution('&copy; <a href="http://www.mapbox.com/about/maps/">MapBox</a> | &copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>').addTo(privates.map);
            L.control.scale({position: 'bottomright'}).addTo(privates.map);

            L.control.zoom({
                position: 'bottomright'
            }).addTo(privates.map);
            $('#zoomtofit').css('display', 'block');
        } else {
            if (privates.map.activeOverlay) {
                privates.map.removeLayer(privates.map.activeOverlay);
                privates.layerControl.removeLayer(privates.map.activeOverlay);
                privates.map.activeOverlay = null;
            }
        }
    };

    var initPopupTemplate = function (config) {
        if (!privates.template || !_.isEqual(config.columns, privates.columns)) {
            privates.columns = config.columns;
            privates.template = _.template([
                "<table class='table table-bordered'>",
                "   <% _.map(columns, function (col) { %>",
                "     <tr>",
                "       <td><%- col.label %></td>",
                "       <td><%- row[col.column_id] %></td>",
                "     </tr>",
                "   <% }) %>",
                "</table>",
            ].join('\n'));
        }
    };

    module.render = function (config, data, mapContainer) {
        init_map(config, mapContainer);
        initPopupTemplate(config);

        var bad_re = /[a-zA-Z()]+/;
        var points = _.compact(_.map(data, function (row) {
            var val = row[config.location_column_id];
            if (val !== null && !bad_re.test(val)) {
                var latlon = val.split(" ").slice(0, 2);
                return L.marker(latlon).bindPopup(privates.template({row: row, columns: privates.columns}));
            }
        }));
        if (points.length > 0) {
            var overlay = L.featureGroup(points);
            privates.layerControl.addOverlay(overlay, config.layer_name);
            overlay.addTo(privates.map);
            privates.map.activeOverlay = overlay;
            hqImport("reports/js/maps_utils").zoomToAll(privates.map);
        }
    };

    return module;
});
