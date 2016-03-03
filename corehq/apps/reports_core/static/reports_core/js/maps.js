/*globals hqDefine */
hqDefine('reports_core/js/maps.js', function () {
    var module = {};

    var getTileLayer = function (layerId, accessToken) {
        return L.tileLayer('https://api.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
            id: layerId,
            accessToken: accessToken,
            maxZoom: 17
        });
    };

    module.init_map = function (config, mapContainer) {
        if (!module.hasOwnProperty('map')) {
            mapContainer.show();
            mapContainer.empty();
            var streets = getTileLayer('mapbox.streets', config.mapboxAccessToken),
                satellite = getTileLayer('mapbox.satellite', config.mapboxAccessToken);

            module.map = L.map(mapContainer[0], {
                trackResize: false,
                layers: [streets]
            }).setView([0, 0], 3);

            L.control.scale().addTo(module.map);

            var baseMaps = {};
            baseMaps[gettext("Streets")] = streets;
            baseMaps[gettext("Satellite")] = satellite;

            module.layerControl = L.control.layers(baseMaps);
            module.layerControl.addTo(module.map);

            new ZoomToFitControl().addTo(module.map);
            $('#zoomtofit').css('display', 'block');
        } else {
            if (module.map.activeOverlay) {
                module.map.removeLayer(module.map.activeOverlay);
                module.layerControl.removeLayer(module.map.activeOverlay);
                module.map.activeOverlay = null;
            }
        }
    };

    module.initPopupTempate = function (config) {
        if (!module.template) {
            var rows = _.map(config.columns, function (col) {
                var tr = _.template("<tr><td><%= label %></td>")(col);
                tr += "<td><%= " + col.column_id + "%></td></tr>";
                return tr;
            });
            var table = '<table class="table table-bordered"><%= rows %></table>';
            var template = _.template(table)({rows: rows.join('')});
            module.template = _.template(template);
        }
    };

    module.render = function (config, data, mapContainer) {
        module.init_map(config, mapContainer);
        module.initPopupTempate(config);

        var bad_re = /[a-zA-Z()]+/;
        var points = _.compact(_.map(data, function (row) {
            var val = row[config.location_column_id];
            if (val !== null && !bad_re.test(val)) {
                var latlon = val.split(" ").slice(0, 2);
                return L.marker(latlon).bindPopup(module.template(row));
            }
        }));
        if (points.length > 0) {
            var overlay = L.featureGroup(points);
            module.layerControl.addOverlay(overlay, config.layer_name);
            overlay.addTo(module.map);
            module.map.activeOverlay = overlay;
            zoomToAll(module.map);
        }
    };

    return module;
});
