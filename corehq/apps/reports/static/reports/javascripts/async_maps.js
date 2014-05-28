// a map control map that lists the various display metrics for this report
// and allows you to select and display them
MetricsControl = L.Control.extend({
    options: {
        position: 'bottomleft'
    },

    onAdd: function(map) {
        this.activeMetric = null;

        this.$div = $('#metrics');
        this.div = this.$div[0];
        L.DomEvent.disableClickPropagation(this.div);
        this.$div.show();

        this.init();

        var m = this;
        map.on('popupopen', function(e) {
            var $popup = $(e.popup._container);
            var metric = m.activeMetric;
            if (metric == null) {
                return;
            }

            // highlight in detail popup
            $popup.find('.data').removeClass('detail_active');
            forEachDimension(metric, function(type, meta) {
                $popup.find('.data-' + meta.column).addClass('detail_active');
            });
        });

        return this.div;
    },

    init: function() {
        var koModel = new MetricsViewModel(this);
        var metrics = $('#metrics')[0];
        ko.cleanNode(metrics);
        ko.applyBindings(koModel, metrics);
        koModel.load(this.options.metrics);
    },

    // TODO support an explicit 'show just markers again' option

    render: function(metric) {
        this.activeMetric = metric;

        var m = this;
        loadData(this._map, this.options.data, makeDisplayContext(metric, function(f) {
            m.options.info.setActive(f, m.activeMetric);
        }));

        this.options.legend.render(metric);
    }
});

// main entry point
function mapsInit(context) {
    if (map_obj === undefined) {
        var map = initMap($('#map'), context.layers, [30., 0.], 2);
    } else {
        map = map_obj;
    }
    initData(context.data, context.config);
    $.each(context.data.features, function(i, e) {
        e.$tr = $($(".tabular tbody tr")[i])
    });
    for (var point in points._layers) {
        if (points._layers.hasOwnProperty(point)){
            map.removeLayer(points._layers[point]);
        }
    }
    initMetrics(map, undefined, context.data, context.config);
    return map;
}

// initialize leaflet map
function initMap($div, layers, default_pos, default_zoom) {
    map_obj = L.map($div.attr('id'), {trackResize: false}).setView(default_pos, default_zoom);
    initLayers(map_obj, layers);

    new ZoomToFitControl().addTo(map_obj);
    new ToggleTableControl().addTo(map_obj);
    L.control.scale().addTo(map_obj);

    return map_obj;
}

// render a display metric to the map
function loadData(map, data, display_context) {
    if (map.activeOverlay) {
        map.removeLayer(map.activeOverlay);
        map.activeOverlay = null;
    }

    points = L.geoJson(data, display_context);

    points.addTo(map);
    map.activeOverlay = points;
}