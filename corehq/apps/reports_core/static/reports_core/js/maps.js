var maps = (function() {
    var fn = {};

    fn.init_map = function (config, mapContainer) {
        if (!fn.hasOwnProperty('map')) {
            //L.Icon.Default.imagePath = config.resourceUrl;

            fn.map = L.map(mapContainer, {trackResize: false}).setView([0, 0], 3);
            var mapId = 'mapbox.streets';
            var accessToken = 'pk.eyJ1IjoiY3p1ZSIsImEiOiJjaWgwa3U5OXIwMGk3a3JrcjF4cjYwdGd2In0.8Tys94ISZlY-h5Y4W160RA';
            L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
                maxZoom: 18,
                id: mapId,
                accessToken: accessToken
            }).addTo(fn.map);
            L.control.scale().addTo(fn.map);

            fn.layerControl = L.control.layers();
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
        mapContainer.show();
        mapContainer.empty();
        fn.init_map(config, mapContainer[0]);
        fn.initPopupTempate(config);


        var points = _.compact(_.map(data, function(row){
            var val = row[config.location_column_id];
            if (val !== null) {
                var latlon = val.split(" ").slice(0, 2);
                return L.marker(latlon).bindPopup(fn.template(row));
            }
        }));
        var overlay = L.featureGroup(points);
        fn.layerControl.addOverlay(overlay, config.layer_name);
        overlay.addTo(fn.map);
        fn.map.activeOverlay = overlay;
        zoomToAll(fn.map);
    };

    return fn;
})();
