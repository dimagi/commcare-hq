/*globals hqDefine */
hqDefine('reports_core/js/maps', function () {
    var module = {},
        privates = {};

    var getTileLayer = function (layerId, accessToken) {
        return L.tileLayer('https://api.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
            id: layerId,
            accessToken: accessToken,
            maxZoom: 17,
        });
    };

    var init_map = function (config, mapContainer) {
        if (!privates.hasOwnProperty('map')) {
            mapContainer.show();
            mapContainer.empty();
            var streets = getTileLayer('mapbox.streets', config.mapboxAccessToken),
                satellite = getTileLayer('mapbox.satellite', config.mapboxAccessToken);

            privates.map = L.map(mapContainer[0], {
                trackResize: false,
                layers: [streets],
            }).setView([0, 0], 3);

            L.control.scale().addTo(privates.map);

            var baseMaps = {};
            baseMaps[gettext("Streets")] = streets;
            baseMaps[gettext("Satellite")] = satellite;

            privates.layerControl = L.control.layers(baseMaps);
            privates.layerControl.addTo(privates.map);

            new ZoomToFitControl().addTo(privates.map);
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
            var rows = _.map(privates.columns, function (col) {
                var tr = _.template("<tr><td><%= label %></td>")(col);
                tr += "<td><%= " + col.column_id + "%></td></tr>";
                return tr;
            });
            var table = '<table class="table table-bordered"><%= rows %></table>';
            var template = _.template(table)({rows: rows.join('')});
            privates.template = _.template(template);
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
                return L.marker(latlon).bindPopup(privates.template(row));
            }
        }));
        if (points.length > 0) {
            var overlay = L.featureGroup(points);
            privates.layerControl.addOverlay(overlay, config.layer_name);
            overlay.addTo(privates.map);
            privates.map.activeOverlay = overlay;
            zoomToAll(privates.map);
        }
    };

    return module;
});
