
DISPLAY_DIMENSIONS = ['size', 'color', 'icon'];

function forEachDimension(metric, callback) {
    $.each(DISPLAY_DIMENSIONS, function(i, e) {
        if (typeof metric[e] == 'object') {
            callback(e, metric[e]);
        }
    });
}

// iterate over all metrics, which can potentially be stored in a tree structure
function forEachMetric(metrics, callback) {
    $.each(metrics, function(i, e) {
        if (e.group) {
            forEachMetric(e.children, callback);
        } else {
            callback(e);
        }
    });
}

function MetricsViewModel(control) {
    var model = this;
    
    this.root = ko.observable();
    this.defaultMetric = null;
    
    this.load = function(metrics) {
        this.root(new MetricModel({title: '_root', children: metrics}, null, this));
        this.root().expanded(true);

        if (this.defaultMetric) {
            this.defaultMetric.onclick();
        } else {
            this.renderMetric(null);
        }
    }

    this.renderMetric = function(metric) {
        control.render(metric);
    }

    this.unselectAll = function() {
        var unselect = function(node) {
            $.each(node.children(), function(i, e) {
                unselect(e);
            });
            node.selected(false);
        }
        unselect(this.root());
    }
}

function MetricModel(data, parent, root) {
    var m = this;
    
    this.metric = null;
    this.name = ko.observable();
    this.children = ko.observableArray();
    this.expanded = ko.observable(false);
    this.selected = ko.observable(false);
    this.parent = parent;

    this.group = ko.computed(function() {
        return this.children().length > 0;
    }, this);
    
    this.onclick = function() {
        if (this.group()) {
            this.toggle();
        } else {
            this.select();
            root.renderMetric(this.metric);
        }
    }

    this.toggle = function() {
        this.expanded(!this.expanded());
    }

    this.select = function() {
        root.unselectAll();
        
        var node = this;
        while (node != null) {
            node.selected(true);
            node.expanded(true);
            node = node.parent;
        }
    }

    this.load = function(data) {
        this.metric = data;
        this.name(data.title);
        this.children($.map(data.children || [], function(e) {
            return new MetricModel(e, m, root);
        }));
        if (data['default']) {
            root.defaultMetric = this;
        }
    }

    this.load(data);
}

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
        ko.applyBindings(koModel, $('#metrics')[0]);
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
    },
});

LegendControl = L.Control.extend({
    options: {
        position: 'bottomright'
    },
    
    onAdd: function(map) {
        this.$div = $('#legend');
        this.div = this.$div[0];
        return this.div;
    },
    
    render: function(metric) {
        if (metric == null) {
            this.$div.hide();
            return;
        }
        
        this.$div.show();
        this.$div.empty();
        renderLegend(this.$div, metric, this.options.config);
    },
});

HeadsUpControl = L.Control.extend({
    options: {
        position: 'bottomright'
    },
    
    onAdd: function(map) {
        this.$div = $('#info');
        this.div = this.$div[0];
        return this.div;
    },
    
    setActive: function(feature, metric) {
        if (feature == null ||
            (metric == null && !this.options.config.name_column)) { // nothing to show
            this.$div.hide();
            return;
        }
        
        var cols = [];
        if (metric != null) {
            forEachDimension(metric, function(type, meta) {
                var col = meta.column;
                if (cols.indexOf(col) == -1) {
                    cols.push(col);
                }
            });
        }

        var context = detailContext(feature, this.options.config, cols);
        var TEMPLATE = $('#info_popup').text();
        var template = _.template(TEMPLATE);
        var content = template(context);
        this.$div.html(content);
        this.$div.show();
    },
});

// a control button that will fit the map viewport to the currently displayed data
ZoomToFitControl = L.Control.extend({
    options: {
        position: 'topright'
    },

    onAdd: function(map) {
        this.$div = $('<div></div>');
        this.$div.addClass('leaflet-control-layers');
        var $inner = $('<div></div>');
        $inner.addClass('leaflet-control-layers-toggle');
        $inner.addClass('zoomtofit');
        this.$div.append($inner);
        $inner.click(function() {
            zoomToAll(map);
        });
        return this.$div[0];
    }
});


// main entry point
function mapsInit(context) {
    var map = initMap($('#map'), context.layers, [30., 0.], 2);
    initData(context.data, context.config);
    initMetrics(map, context.data, context.config);
    return map;
}

// initialize leaflet map
function initMap($div, layers, default_pos, default_zoom) {
    var map = L.map($div.attr('id')).setView(default_pos, default_zoom);
    initLayers(map, layers);

    new ZoomToFitControl().addTo(map);
    L.control.scale().addTo(map);

    return map;
}

function initLayers(map, layers_spec) {
    LAYER_FAMILIES = {
        'fallback': {
            url_template: 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            args: {
                attribution: '<a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            }
        },
        'mapbox': {
            url_template: 'http://api.tiles.mapbox.com/v3/{apikey}/{z}/{x}/{y}.png',
            args: {
                attribution: '<a href="http://www.mapbox.com/about/maps/">MapBox</a>'
            }
        }
    }

    var mkLayer = function(spec) {
        if (spec.family) {
            var family_spec = LAYER_FAMILIES[spec.family];
            spec.url_template = family_spec.url_template;
            spec.args = spec.args || {};
            $.each(family_spec.args || {}, function(k, v) {
                spec.args[k] = v;
            });
        }
        return L.tileLayer(spec.url_template, spec.args);
    }

    var layers = {};
    var defaultLayer = null;
    $.each(layers_spec, function(k, v) {
        layers[k] = mkLayer(v);
        if (v['default']) {
            defaultLayer = k;
        }
    });
    L.control.layers(layers).addTo(map);

    if (!defaultLayer) {
        defaultLayer = _.keys(layers)[0];
    }
    map.addLayer(layers[defaultLayer]);
}

// perform any pre-processing of the raw data
function initData(data, config) {
    // instantiate data formatting functions
    config._fmt = {};
    $.each(config.numeric_format || {}, function(k, v) {
        try {
            // TODO allow these functions to access other properties for that row?
            config._fmt[k] = eval('(function(x) { ' + v + '})');
        } catch (err) {
            console.log('error in formatter function [' + v + ']');
        }
    });

    // make a default detail view if not specified
    if (config.detail_columns == null) {
        config.detail_columns = getAllCols(config, data);
    }

    // pre-cache popup detail
    $.each(data.features, function(i, e) {
        e.popupContent = formatDetailPopup(e, config);
    });
}

// set up the configured display metrics
function initMetrics(map, data, config) {
    // auto-generate metrics from data columns (if none provided)
    if (!config.metrics || config.debug) {
        autoConfiguration(config, data);
    }

    // set sensible defaults for metric parameters (if omitted)
    forEachMetric(config.metrics, function(metric) {
        setMetricDefaults(metric, data, config);
    });

    // necessary closures (TODO make a class?)
    forEachMetric(config.metrics, function(metric) {
        forEachDimension(metric, function(type, meta) {
            meta._enumCaption = function(val, labelFallbacks) {
                return getEnumCaption(meta.column, val, config, labelFallbacks);
            };
            meta._formatNum = function(val) {
                return formatValue(meta.column, val, config);
            };
        });
    });

    var l = new LegendControl({config: config}).addTo(map);
    var h = new HeadsUpControl({config: config}).addTo(map);
    var m = new MetricsControl({metrics: config.metrics, data: data, legend: l, info: h}).addTo(map);

    zoomToAll(map);
}

// render a display metric to the map
function loadData(map, data, display_context) {
    if (map.activeOverlay) {
        map.removeLayer(map.activeOverlay);
        map.activeOverlay = null;
    }

    var points = L.geoJson(data, display_context);
    points.addTo(map);
    map.activeOverlay = points;
}

function zoomToAll(map) {
    if (map.activeOverlay) {
        map.fitBounds(map.activeOverlay.getBounds(), {padding: [60, 60]});
    }
}

// generate the proper geojson styling for the given display metric
function makeDisplayContext(metric, setActiveFeature) {
    return {
        filter: function(feature, layer) {
            if (feature.geometry.type == "Point") {
                feature._conf = markerFactory(metric, feature.properties);
            } else {
                feature._conf = featureStyle(metric, feature.properties);
            }
            // TODO support placeholder markers for 'null' instead of hiding entirely?
            return (feature._conf != null);
        },
        style: function(feature) {
            return feature._conf;
        },
        pointToLayer: function (feature, latlng) {
            return feature._conf(latlng);
        },
        onEachFeature: function(feature, layer) {
            layer.bindPopup(feature.popupContent, {
                maxWidth: 600,
            });

            if (feature.geometry.type != 'Point') {
                layer._activate = function() {
                    layer.setStyle(ACTIVE_STYLE);
                };
                layer._deactivate = function() {
                    layer.setStyle(feature._conf);
                };
            }

            layer.on({
                mouseover: function(e) {
                    if (layer._activate) {
                        layer._activate();
                        if (layer.bringToFront) {
                            // normal markers don't have this method; mimic with 'riseOnHover'
                            layer.bringToFront();
                        }
                    }
                    setActiveFeature(feature);
                },
                mouseout: function(e) {
                    if (layer._deactivate) {
                        layer._deactivate();
                    }
                    setActiveFeature(null);
                },
            });
        }
    }
}

function markerFactory(metric, props) {
    if (metric == null) {
        return defaultMarker(props);
    }

    try {
        if (metric.icon) {
            return iconMarker(metric, props);
        } else {
            return circleMarker(metric, props);
        }
    } catch (err) {
        // marker cannot be rendered due to data error
        // TODO log or display 'error' marker?
        console.log(err);
        return null;
    }
}

function featureStyle(metric, props) {
    if (metric == null) {
        return defaultFeatureStyle(props);
    }

    try {
        var fill = getColor(metric.color, props);
        if (fill == null) {
            return null;
        }

        return {
            color: "#000",
            weight: 1,
            opacity: 1,
            fillColor: fill.color,
            fillOpacity: fill.alpha
        };
    } catch (err) {
        // marker cannot be rendered due to data error
        // TODO log or display 'error' marker?
        console.log(err);
        return null;
    }
}

ACTIVE_STYLE = {
    color: '#ff0',
    weight: 2,
    opacity: 1
};

function mkMarker(latlng, options) {
    options = options || {};
    options.riseOnHover = true;

    var marker = new L.marker(latlng, options);
    marker._activate = function() {
        $(marker._icon).addClass('glow');
    };
    marker._deactivate = function() {
        $(marker._icon).removeClass('glow');
    };

    return marker;
}

function defaultMarker() {
    return mkMarker;
}

function defaultFeatureStyle() {
    return {
        color: "#000",
        weight: 1,
        opacity: .8,
        fillColor: '#888',
        fillOpacity: .3
    };
}

function circleMarker(metric, props) {
    var size = getSize(metric.size, props);
    var fill = getColor(metric.color, props);
    if (size == null || fill == null) {
        return null;
    }

    return function(latlng) {
        var style = {
            color: "#000",
            weight: 1,
            opacity: 1,
            radius: size,
            fillColor: fill.color,
            fillOpacity: fill.alpha
        };
        var marker = L.circleMarker(latlng, style);
        marker._activate = function() {
            marker.setStyle(ACTIVE_STYLE);
        };
        marker._deactivate = function() {
            marker.setStyle(style);
        };
        return marker;
    };
}

function iconMarker(metric, props) {
    var icon = getIcon(metric.icon, props);
    if (icon == null) {
        return null;
    }

    return function(latlng) {
        var marker = mkMarker(latlng, {
            icon: L.icon({
                iconUrl: icon.url,
            })
        });
        var img = new Image();
        img.onload = function() {
            // leaflet needs explicit icon dimensions
            marker.setIcon(L.icon({
                iconUrl: icon.url,
                iconSize: [this.width, this.height]
            }));
        };
        img.src = icon.url;
        
        return marker;
    }
}

DEFAULT_SIZE = 10;
DEFAULT_MIN_SIZE = 3;
function getSize(meta, props) {
    if (meta == null) {
        return DEFAULT_SIZE;
    } else if (isNumeric(meta)) {
        return meta;
    } else {
        var val = getPropValue(props, meta);
        if (isNull(val)) {
            return null;
        } else if (!isNumeric(val)) {
            throw new TypeError('numeric value required [' + val + ']');
        }

        return Math.min(Math.max(markerSize(val, meta.baseline), meta.min || DEFAULT_MIN_SIZE), meta.max || 9999);
    }
}

// scale value with area of marker
function markerSize(val, baseline) {
    return DEFAULT_SIZE * Math.sqrt(val / baseline);
}

DEFAULT_COLOR = 'rgba(255, 120, 0, .8)';
function getColor(meta, props) {
    var c = (function() {
        if (meta == null) {
            return DEFAULT_COLOR;
        } else if (typeof meta == 'string') {
            return meta;
        } else {
            var val = getPropValue(props, meta);
            if (meta.categories) {
                return matchCategories(val, meta.categories);
            } else {
                if (isNull(val)) {
                    return null;
                } else if (!isNumeric(val)) {
                    throw new TypeError('numeric value required [' + val + ']');
                } else {
                    return matchSpline(val, meta.colorstops, blendColor);
                }
            }
        }
    })();
    if (c == null) {
        return null;
    }

    c = $.Color(c);
    return {color: c.toHexString(), alpha: c.alpha()};
}

DEFAULT_ICON_URL = '/static/reports/css/leaflet/images/default_custom.png';
function getIcon(meta, props) {
    //TODO support css sprites
    var icon = (function() {
        if (typeof meta == 'string') {
            return meta;
        } else {
            var val = getPropValue(props, meta);
            return matchCategories(val, meta.categories);
        }
    })();
    if (icon == null) {
        return null;
    }
    return {url: icon};
}

function getPropValue(props, meta) {
    var val = props[meta.column];
    if (isNull(val)) {
        return null;
    }

    if (meta.thresholds) {
        if (!isNumeric(val)) {
            throw new TypeError('numeric value required [' + val + ']');
        }
        val = matchThresholds(val, meta.thresholds);
    }
    return val;
}



function detailContext(feature, config, cols) {
    prop_cols = cols || _.keys(feature.properties);
    detail_cols = cols || config.detail_columns || [];

    var formatForDisplay = function(col, datum) {
        var fallback = {_null: '\u2014'};
        fallback[datum] = formatValue(col, datum, config);
        return getEnumCaption(col, datum, config, fallback);
    };
    var displayProperties = {};
    $.each(prop_cols, function(i, k) {
        var v = feature.properties[k];
        displayProperties[k] = formatForDisplay(k, v);
    });

    var context = {
        props: displayProperties,
        name: (config.name_column ? feature.properties[config.name_column] : null),
    };
    context.detail = [];
    $.each(detail_cols, function(i, e) {
        context.detail.push({
            slug: e, // FIXME this will cause problems if column keys have weird chars or spaces
            label: getColumnTitle(e, config),
            value: displayProperties[e],
        });
    });
    return context;
}

function formatDetailPopup(feature, config) {
    var DEFAULT_TEMPLATE = $('#default_detail_popup').text();
    var TEMPLATE = config.detail_template || DEFAULT_TEMPLATE;

    var template = _.template(TEMPLATE);
    var content = template(detailContext(feature, config));
    return content;
}

// attempt to set sensible defaults for any missing parameters in the metric definitions
function setMetricDefaults(metric, data, config) {
    if (!metric.title) {
        var varcols = [];
        forEachDimension(metric, function(type, meta) {
            var col = meta.column;
            if (varcols.indexOf(col) == -1) {
                varcols.push(col);
            }
        });
        metric.title = $.map(varcols, function(e) { return getColumnTitle(e, config); }).join(' / ');
    }

    if (typeof metric.size == 'object') {
        if (!metric.size.baseline) {
            var stats = summarizeColumn(metric.size, data);
            metric.size.baseline = (stats.mean || 1);
        }
    }

    if (typeof metric.color == 'object') {
        if (!metric.color.categories && !metric.color.colorstops) {
            var stats = summarizeColumn(metric.color, data);
            var numeric_data = (!metric.color.thresholds && !stats.nonnumeric);
            if (numeric_data) {
                metric.color.colorstops = (magnitude_based_field(stats) ?
                                           [
                                               [0, 'rgba(20, 20, 20, .8)'],
                                               [stats.max || 1, DEFAULT_COLOR],
                                           ] :
                                           [
                                               [stats.min, 'rgba(0, 0, 255, .8)'],
                                               [stats.min == stats.max ? 0 : stats.max, 'rgba(255, 0, 0, .8)'],
                                           ]);
            } else {
                if (metric.color.thresholds) {
                    var enums = metric.color.thresholds.slice(0);
                    enums.splice(0, 0, '-');
                } else {
                    var enums = stats.distinct;
                }

                var cat = {};
                $.each(enums, function(i, e) {
                    var hue = i * 360. / enums.length;
                    cat[e] = 'hsla(' + hue + ', 100%, 50%, .8)';
                });
                metric.color.categories = cat;
            }
        }
    }

    if (typeof metric.icon == 'object') {
        if (!metric.icon.categories) {
            metric.icon.categories = {_other: DEFAULT_ICON_URL};
        }
    }
}

function getAllCols(config, data) {
    var ignoreCols = [config.name_column];
    var _cols = {};
    $.each(data.features, function(i, e) {
        $.each(e.properties, function(k, v) {
            if (ignoreCols.indexOf(k) == -1) {
                _cols[k] = true;
            }
        });
    });
    return _.sortBy(_.keys(_cols), function(e) { return getColumnTitle(e, config); });
}

function autoConfiguration(config, data) {
    var metrics = $.map(getAllCols(config, data), function(e) {
        var meta = {column: e};
        var stats = summarizeColumn(meta, data);
        var metric = {}
        if (stats.nonnumeric || !magnitude_based_field(stats) || stats.nonpoint) {
            metric.color = meta;
        } else {
            metric.size = meta;
        }
        return metric;
    });
    // metrics may already exist if we're in debug mode
    config.metrics = (config.metrics || []).concat([{title: 'Auto', group: true, children: metrics}]);
}

function summarizeColumn(meta, data) {
    // cache the computed results
    if (!meta._stats) {
        meta._stats = _summarizeColumn(meta, data);
        //console.log(meta.column, meta._stats);
    }
    return meta._stats;
}

// compute statistics on a given column of data for the purpose of determining
// sensible styling defaults
function _summarizeColumn(meta, data) {
    var _uniq = {};
    var sum = 0;
    var count = 0; // of numeric values only
    var min = null;
    var max = null;
    var nonnumeric = false;
    var nonpoint = false;

    var iterate = function(callback) {
        $.each(data.features, function(i, e) {
            var val = getPropValue(e.properties, meta);
            if (isNull(val)) {
                return;
            }

            var numeric = isNumeric(val);
            var polygon = e.geometry.type != 'Point';
            callback(numeric ? +val : val, numeric, polygon);
        });
    }

    iterate(function(val, numeric, polygon) {
        _uniq[val] = true;
        if (numeric) {
            count++;
            sum += val;
            min = (min == null ? val : Math.min(min, val));
            max = (max == null ? val : Math.max(max, val));
        } else {
            nonnumeric = true;
        }
        if (polygon) {
            nonpoint = true;
        }
    });
    var uniq = [];
    $.each(_uniq, function(k, v) {
        uniq.push(k);
    });
    uniq.sort();

    var mean = (count > 0 ? sum / count : null);
    var stdev = null;
    if (count > 1) {
        var _accum = 0;
        iterate(function(val, numeric) {
            if (numeric) {
                _accum += Math.pow(val - mean, 2.);
            }
        });
        stdev = Math.sqrt(_accum / (count - 1));
    }

    return {
        distinct: uniq,
        mean: mean,
        stdev: stdev,
        min: min,
        max: max,
        nonnumeric: nonnumeric,
        nonpoint: nonpoint,
    };
}

// based on the results of summarizeColumn, determine if this column is better
// represented as a magnitude (0-max) or narrower range (min-max)
function magnitude_based_field(stats) {
    if (stats.min < 0) {
        return false;
    } else if (stats.stdev != null && stats.stdev > 0) {
        var effective_range = Math.max(stats.max, 0) - Math.min(stats.min, 0);
        return (stats.stdev / effective_range > .1);
    } else {
        return true;
    }
}

function getEnumValues(meta) {
    var labelFallbacks = {};
    var toLabel = function(e) {
        return meta._enumCaption(e, labelFallbacks);
    }

    if (meta.thresholds) {
        var enums = meta.thresholds.slice(0);
        enums.splice(0, 0, '-');

        $.each(enums, function(i, e) {
            labelFallbacks[e] = (function() {
                if (i == 0) {
                    return '< ' + meta._formatNum(enums[1]);
                } else if (i == enums.length - 1) {
                    return '> ' + meta._formatNum(e);
                } else {
                    return meta._formatNum(e) + ' \u2013 ' + meta._formatNum(enums[i + 1]);
                }
            })();
        });

        if (meta.categories && meta.categories._null) {
            enums.push('_null');
        }
    } else {
        var enums = _.keys(meta.categories);
        var special = _.filter(enums, function(e) { return e[0] == '_'; });
        enums = _.filter(enums, function(e) { return e[0] != '_'; });

        enums = _.sortBy(enums, toLabel);
        // move special categories to the end
        $.each(['_other', '_null'], function(i, e) {
            if (special.indexOf(e) != -1) {
                enums.push(e);
            }
        });
    }

    return $.map(enums, function(e, i) { return {label: toLabel(e), value: e}; });
}

// FIXME i18n
OTHER_LABEL = 'Other';
NULL_LABEL = 'No Data';
function getEnumCaption(column, value, config, fallbacks) {
    if (isNull(value)) {
        value = '_null';
    }
    var captions = (config.enum_captions || {})[column] || {};

    fallbacks = fallbacks || {};
    $.each({'_other': OTHER_LABEL, '_null': NULL_LABEL}, function(k, v) {
        fallbacks[k] = fallbacks[k] || v;
    });
    var fallback = fallbacks[value] || value;

    return captions[value] || fallback;
}

function formatValue(column, value, config) {
    if (isNull(value)) {
        return null;
    }

    var formatter = config._fmt[column];
    return (formatter ? formatter(value) : value);
}

function getColumnTitle(col, config) {
    return (config.column_titles || {})[col] || col;
}




function renderLegend($e, metric, config) {
    forEachDimension(metric, function(type, meta) {
        var col = meta.column;
        var $h = $('<h4>');
        $h.text(getColumnTitle(col, config));
        $e.append($h);

        $div = $('<div>');
        ({      
            size: sizeLegend,
            color: colorLegend,
            icon: iconLegend,
        })[type]($div, meta);
        $e.append($div);
    });
};

function sizeLegend($e, meta) {
    var rows = $.map([.5, 0, -.5], function(e) {
        var val = niceRoundNumber(Math.pow(10., e) * meta.baseline);
        return {
            val: val,
            valfmt: meta._formatNum(val),
            radius: markerSize(val, meta.baseline),
        };
    });

    var $rendered = $(_.template($('#legend_size').text())({entries: rows}));

    $.each(rows, function(i, e) {
        var $r = $rendered.find('#sizerow-' + i);
        var diameter = 2 * e.radius;
        $r.find('.circle').css('width', diameter + 'px');
        $r.find('.circle').css('height', diameter + 'px');
    });

    $e.append($rendered);
}

function colorLegend($e, meta) {
    if (meta.colorstops) {
        colorScaleLegend($e, meta);
    } else {
        enumLegend($e, meta, function($cell, value) {
            $cell.css('background-color', value);
        });
    }
}

function iconLegend($e, meta) {
    enumLegend($e, meta, function($cell, value) {
        var $icon = $('<img>');
        $icon.attr('src', value);
        $cell.append($icon);
    });
}

SCALEBAR_HEIGHT = 150; //px
SCALEBAR_WIDTH = 20; // TODO seems like we want to tie this to em-height instead
TICK_SPACING = 40; //px
MIN_BUFFER = 15; //px
function colorScaleLegend($e, meta) {
    var min = meta.colorstops[0][0];
    var max = meta.colorstops.slice(-1)[0][0];
    var range = max - min;
    var step = range / (SCALEBAR_HEIGHT - 1);

    var $canvas = make_canvas(SCALEBAR_WIDTH, SCALEBAR_HEIGHT);
    var ctx = $canvas[0].getContext('2d');
    for (var i = 0; i < SCALEBAR_HEIGHT; i++) {
        var k = i / (SCALEBAR_HEIGHT - 1);
        var x = blendLinear(min, max, k);
        var y = $.Color(matchSpline(x, meta.colorstops, blendColor)).toRgbaString();
        ctx.fillStyle = y;
        ctx.fillRect(0, SCALEBAR_HEIGHT - 1 - i, SCALEBAR_WIDTH, 1);
    }

    var interval = niceRoundNumber(step * TICK_SPACING);
    var tickvals = [];
    for (var k = interval * Math.ceil(min / interval); k <= max; k += interval) {
        tickvals.push(k);
    }
    var buffer_dist = step * MIN_BUFFER;
    if (tickvals[0] - min > buffer_dist) {
        tickvals.splice(0, 0, min);
    }
    if (max - tickvals.slice(-1)[0] > buffer_dist) {
        tickvals.push(max);
    }

    var ticks = $.map(tickvals, function(e) {
        return {label: meta._formatNum(e), coord: (1. - (e - min) / range) * SCALEBAR_HEIGHT};
    });

    var $rendered = $(_.template($('#legend_colorscale').text())({ticks: ticks}));
    $rendered.find('#scalebar').append($canvas);
    $e.append($rendered);
}

function enumLegend($e, meta, renderValue) {
    var enums = getEnumValues(meta);

    var $rendered = $(_.template($('#legend_enum').text())({enums: enums}));

    $.each(enums, function(i, e) {
        var $r = $rendered.find('#enumrow-' + i);
        var cat = matchCategories(e.value, meta.categories);
        renderValue($r.find('.enum'), cat);
    });

    $e.append($rendered);
}



function isNumeric(x) {
    return (!isNull(x) && !isNaN(+x));
}

function isNull(x) {
    return (x === undefined || x === null || x === '');
}



// convert a numerical value into an enumerated value based on cutoff thresholds
// 'thresholds' must be in ascending order
// e.g., thresholds of [2, 5, 10] creates 4 buckets: <2; [2, 5); [5, 10); >=10
// return the lower bound of the matching bucket, or '-' for the lowest bucket
function matchThresholds(val, thresholds, returnIndex) {
    var cat = (returnIndex ? -1 : '-');
    $.each(thresholds, function(i, e) {
        if (e <= val) {
            cat = (returnIndex ? i : e);
        } else {
            return false;
        }
    });
    return cat;
}

// match an enumerated value to its display value
// 'categories' is a mapping of enum values to display values
// 'categories' may define a mapping for '_other', which will be used for
// all values that do not have an explicit value assigned, otherwise
// those values will resolve to null
// 'categories' may also define a special mapping '_null' which will match
// null values
function matchCategories(val, categories) {
    if (isNull(val)) {
        return categories._null;
    } else if (categories.hasOwnProperty(val)) {
        return categories[val];
    } else {
        return categories._other;
    }
}

// linearly interpolate a value along a spline specified by 'stops'
// 'stops' is a list of [x, y] coordinates that map out a line
// returns the y-value of this line for x-value = val
// blendfunc may be provided if the y-values are not scalar
function matchSpline(val, stops, blendfunc) {
    blendfunc = blendfunc || blendLinear;

    stops = _.sortBy(stops, function(e) { return e[0]; });
    var x = [];
    var y = [];
    $.each(stops, function(i, e) {
        x.push(e[0]);
        y.push(e[1]);
    });

    var bracket = matchThresholds(val, x);
    var lo = (bracket == '-' ? -1 : x.indexOf(bracket));
    var hi = lo + 1;
    if (lo == -1) {
        return y[hi];
    } else if (hi == x.length) {
        return y[lo];
    } else {
        return blendfunc(y[lo], y[hi], (val - x[lo]) / (x[hi] - x[lo]));
    }
}

// linearly interpolate two values (a and b). k = 0.0 - 1.0
function blendLinear(a, b, k) {
    return a * (1 - k) + b * k;
}

// linearly blend two colors together. a and b are colors; return a color
// 'k' distance (0.0 - 1.0) from a to b.
function blendColor(a, b, k) {
    var GAMMA = 2.2;

    // convert to linear color space and premultiply alpha
    var toLinear = function(c) {
        var channels = $.Color(c).rgba();
        for (var i = 0; i < 3; i++) {
            channels[i] = Math.pow((channels[i] + .5) / 256., GAMMA);
            channels[i] *= channels[3];
        }
        return channels;
    }

    // reverse toLinear()
    var fromLinear = function(channels) {
        for (var i = 0; i < 3; i++) {
            channels[i] /= channels[3];
            channels[i] = Math.floor(256. * Math.pow(channels[i], 1. / GAMMA));
        }
        return $.Color(channels);
    }

    lA = toLinear(a);
    lB = toLinear(b);
    lBlend = [];
    for (var i = 0; i < 4; i++) {
        lBlend.push(blendLinear(lA[i], lB[i], k));
    }
    return fromLinear(lBlend);
}

function niceRoundNumber(x, stops, orderOfMagnitude) {
    var orderOfMagnitude = orderOfMagnitude || 10;
    var stops = stops || [1, 2, 5];
    // numbers will snap to .1, .2, .5, 1, 2, 5, 10, 20, 50, 100, 200, etc.

    var xLog = Math.log(x) / Math.log(orderOfMagnitude);
    var exponent = Math.floor(xLog);
    var xNorm = Math.pow(orderOfMagnitude, xLog - exponent);

    var getStop = function(i) {
        return (i == stops.length ? orderOfMagnitude * stops[0] : stops[i]);
    }
    var cutoffs = $.map(stops, function(e, i) {
        var multiplier = getStop(i + 1);
        var cutoff = Math.sqrt(e * multiplier);
        if (cutoff >= orderOfMagnitude) {
            multiplier /= orderOfMagnitude;
            cutoff /= orderOfMagnitude;
        }
        return {cutoff: cutoff, mult: multiplier};
    });
    cutoffs = _.sortBy(cutoffs, function(co) { return co.cutoff; });

    var bucket = matchThresholds(xNorm, $.map(cutoffs, function(co) { return co.cutoff; }), true);
    var multiplier = (bucket == -1 ? cutoffs.slice(-1)[0].mult / orderOfMagnitude : cutoffs[bucket].mult);
    return Math.pow(orderOfMagnitude, exponent) * multiplier;
}

function testNiceRoundNumber() {
    var test = function(args) {
        var result = niceRoundNumber.apply(this, args);
        console.log(args, result);
    };
    var testStops = function(stops, vals) {
        for (var OoM = -2; OoM < 3; OoM++) {
            $.each(vals, function(i, e) { test([Math.pow(10., OoM) * e, stops]); });
        }
    }

    testStops([1.5, 3, 6], [1, 1.5, 2.1, 2.2, 3, 4.2, 4.3, 6, 9.4, 9.5]); 
    testStops([3, 8], [1, 1.5, 1.6, 3, 4.8, 4.9, 8]);
    testStops([5], [1, 1.5, 1.6, 5]);
    testStops([1], [1, 3.1, 3.2]);
}

// create a (hidden) canvas
function make_canvas(w, h) {
    var $canvas = $('<canvas />');
    $canvas.attr('width', w);
    $canvas.attr('height', h);
    return $canvas;
}




//// OLD STUFF
/*
function canvas_context(canvas) {
    var ctx = canvas.getContext('2d');
    ctx.clear = function() {
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.restore();
    };
    return ctx;
}

// draw to a canvas and export the result as an image (data url)
function render_icon(draw, width, height) {
    var canvas = make_canvas(width, height)[0];
    var ctx = canvas_context(canvas);
    draw(ctx, width, height);
    return canvas.toDataURL('image/png');
}

// create an icon rendered via canvas
function render_marker(draw, w, h, anchor) {
    anchor = anchor || [0, 0];
    return new google.maps.MarkerImage(
        render_icon(draw, w, h),
        new google.maps.Size(w, h),
        new google.maps.Point(0, 0),
        new google.maps.Point(w * .5 * (anchor[0] + 1.), h * .5 * (1. - anchor[1]))
    );
}
*/

