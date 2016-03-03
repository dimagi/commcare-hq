var maps = (function() {
    var fn = {};

    var getTileLayer = function (layerId, accessToken) {
        return L.tileLayer('https://api.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
            id: layerId,
            accessToken: accessToken,
            maxZoom: 17
        });
    };

    fn.init_map = function (config, mapContainer) {
        if (!fn.hasOwnProperty('map')) {
            mapContainer.show();
            mapContainer.empty();
            var streets = getTileLayer('mapbox.streets', config.mapboxAccessToken),
                satellite = getTileLayer('mapbox.satellite', config.mapboxAccessToken);

            fn.map = L.map(mapContainer[0], {
                trackResize: false,
                layers: [streets]
            }).setView([0, 0], 3);

            L.control.scale().addTo(fn.map);

            var baseMaps = {};
            baseMaps[gettext("Streets")] = streets;
            baseMaps[gettext("Satellite")] = satellite;

            fn.layerControl = L.control.layers(baseMaps);
            fn.layerControl.addTo(fn.map);

            new ZoomToFitControl().addTo(fn.map);
            $('#zoomtofit').css('display', 'block');
        } else {
            if (fn.map.activeOverlay) {
                fn.map.removeLayer(fn.map.activeOverlay);
                fn.layerControl.removeLayer(fn.map.activeOverlay);
                fn.map.activeOverlay = null;
            }
        }
    };

    fn.initPopupTempate = function (config) {
        if (!fn.template) {
            var rows = _.map(config.columns, function (col) {
                var tr = _.template("<tr><td><%= label %></td>")(col);
                tr += "<td><%= " + col.column_id + "%></td></tr>";
                return tr;
            });
            var table = '<table class="table table-bordered"><%= rows %></table>';
            var template = _.template(table)({rows: rows.join('')});
            fn.template = _.template(template);
        }
    };

    fn.render = function (config, data, mapContainer) {
        fn.init_map(config, mapContainer);
        fn.initPopupTempate(config);

        var bad_re = /[a-zA-Z()]+/;
        var points = _.compact(_.map(data, function (row) {
            var val = row[config.location_column_id];
            if (val !== null && !bad_re.test(val)) {
                var latlon = val.split(" ").slice(0, 2);
                return L.marker(latlon).bindPopup(fn.template(row));
            }
        }));
        if (points.length > 0) {
            var overlay = L.featureGroup(points);
            fn.layerControl.addOverlay(overlay, config.layer_name);
            overlay.addTo(fn.map);
            fn.map.activeOverlay = overlay;
            zoomToAll(fn.map);
        }
    };

    return fn;
})();
