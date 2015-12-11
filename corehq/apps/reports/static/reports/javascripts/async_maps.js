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
        $(metrics).koApplyBindings(koModel);
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

function clearMap() {
    for(var i in map_obj._layers) {
        if(map_obj._layers[i]._path != undefined) {
            try {
                map_obj.removeLayer(map_obj._layers[i]);
            }
            catch(e) {
                console.log("problem with " + e + map_obj._layers[i]);
            }
        }
    }
}

function clearPoints() {
    for (var point in points._layers) {
        if (points._layers.hasOwnProperty(point)){
            map_obj.removeLayer(points._layers[point]);
        }
    }
}

// main entry point
function mapsInit(context) {
    var map = undefined;
    if (map_obj !== undefined) {
        clearPoints();
        clearMap();
    }
    try {
        map = initMap($('#map'), context.layers, [30., 0.], 2);
    } catch(e) {
        map = map_obj
    }
    initData(context.data, context.config);
    $.each(context.data.features, function(i, e) {
        e.$tr = $($(".tabular tbody tr")[i])
    });

    initMetrics(map, undefined, context.data, context.config);
    $('#zoomtofit').css('display', 'block');
    $('#toggletable').css('display', 'block');
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
