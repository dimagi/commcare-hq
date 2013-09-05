
DISPLAY_DIMENSIONS = ['size', 'color', 'icon'];

function forEachDimension(metric, callback) {
    $.each(DISPLAY_DIMENSIONS, function(i, e) {
	if (typeof metric[e] == 'object') {
	    callback(e, metric[e]);
	}
    });
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

    // TODO support an explicit 'show just markers again' option

    addMetric: function(metric) {
	var $e = $('<div></div>');
	$e.addClass('choice');
	$e.text(metric.title);
	var m = this;
	$e.click(function() {
	    m.activeMetric = metric;
	    m.select($e);
	    m.render(metric);
	});
	this.$div.append($e);
    },

    select: function($e) {
	this.$div.find('div').removeClass('selected');
	if ($e) {
	    $e.addClass('selected');
	}
    },

    render: function(metric) {
	loadData(this._map, this.options.data, makeDisplayContext(metric));
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
    var map = initMap($('#map'), [30., 0.], 2, 'Map');
    initData(context.data, context.config);
    initMetrics(map, context.data, context.config);
    return map;
}

// initialize leaflet map
function initMap($div, default_pos, default_zoom, default_layer) {
    var map = L.map($div.attr('id')).setView(default_pos, default_zoom);

    var mapboxLayer = function(tag) {
	return L.tileLayer('http://api.tiles.mapbox.com/v3/' + tag + '/{z}/{x}/{y}.png', {
	    attribution: '<a href="http://www.mapbox.com/about/maps/">MapBox</a>',
	});
    };

    var layers = {
	// TODO: these tags should probably not be hard-coded
	'Map': mapboxLayer('dimagi.map-0cera12g'),
	'Satellite': mapboxLayer('examples.map-qfyrx5r8'), // note: we need a pay account to use this for real
    }
    L.control.layers(layers).addTo(map);
    map.addLayer(layers[default_layer]);

    new ZoomToFitControl().addTo(map);
    L.control.scale().addTo(map);

    return map;
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

    // pre-cache popup detail
    $.each(data.features, function(i, e) {
	e.popupContent = formatDetailPopup(e, config);
    });
}

// set up the configured display metrics
function initMetrics(map, data, config) {
    if (!config.metrics || config.debug) {
	autoConfiguration(config, data);
    }

    $.each(config.metrics, function(i, e) {
	setMetricDefaults(e, data, config);
    });

    $.each(config.metrics, function(i, e) {
	forEachDimension(e, function(type, meta) {
	    meta._enumCaption = function(val, labelFallbacks) {
		return getEnumCaption(meta.column, val, config, labelFallbacks);
	    };
	    meta._formatNum = function(val) {
		return formatValue(meta.column, val, config);
	    };
	});
    });

    var l = new LegendControl({config: config}).addTo(map);
    var m = new MetricsControl({data: data, legend: l}).addTo(map);

    $.each(config.metrics, function(i, e) {
	m.addMetric(e);
    });

    // load markers and set initial viewport
    m.render(null);
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
function makeDisplayContext(metric) {
    return {
	filter: function(feature, layer) {
	    feature.mkMarker = markerFactory(metric, feature.properties);
	    // TODO support placeholder markers for 'null' instead of hiding entirely?
	    return (feature.mkMarker != null);
	},
	pointToLayer: function (feature, latlng) {
	    return feature.mkMarker(latlng);
	},
	onEachFeature: function(feature, layer) {
            layer.bindPopup(feature.popupContent);
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

function defaultMarker(props) {
    return L.marker;
}

function circleMarker(metric, props) {
    var size = getSize(metric.size, props);
    var fill = getColor(metric.color, props);
    if (size == null || fill == null) {
	return null;
    }

    return function(latlng) {
	return L.circleMarker(latlng, {
	    color: "#000",
	    weight: 1,
	    opacity: 1,
	    radius: size,
	    fillColor: fill.color,
	    fillOpacity: fill.alpha
	});
    };
}

function iconMarker(metric, props) {
    var icon = getIcon(metric.icon, props);
    if (icon == null) {
	return null;
    }

    return function(latlng) {
	var marker = L.marker(latlng, {
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





function formatDetailPopup(feature, config) {
    var DEFAULT_TEMPLATE = $('#default_detail_popup').text();
    var TEMPLATE = config.detail_template || DEFAULT_TEMPLATE;

    var formatForDisplay = function(col, datum) {
	var fallback = {_null: '\u2014'};
	fallback[datum] = formatValue(col, datum, config);
	return getEnumCaption(col, datum, config, fallback);
    };
    var displayProperties = {};
    $.each(feature.properties, function(k, v) {
	displayProperties[k] = formatForDisplay(k, v);
    });

    var context = {props: displayProperties};
    if (config.name_column) {
	context.name = feature.properties[config.name_column];
    }
    context.detail = [];
    $.each(config.detail_columns || [], function(i, e) {
	context.detail.push({
	    slug: e, // FIXME this will cause problems if column names have weird chars or spaces
	    label: getColumnTitle(e, config),
	    value: displayProperties[e],
	});
    });

    var template = _.template(TEMPLATE);
    var content = template(context);
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
	    metric.size.baseline = stats.mean;
	}
    }

    if (typeof metric.color == 'object') {
	if (!metric.color.categories && !metric.color.colorstops) {
	    var stats = summarizeColumn(metric.color, data);
	    var numeric_data = (!metric.color.thresholds && !stats.nonnumeric);
	    if (numeric_data) {
		metric.color.colorstops = (stats.min < 0 ?
					   [
					       [stats.min, 'rgba(0, 0, 255, .8)'],
					       [stats.max, 'rgba(255, 0, 0, .8)'],
					   ] :
					   [
					       [0, 'rgba(20, 20, 20, .8)'],
					       [stats.max, DEFAULT_COLOR],
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

function autoConfiguration(config, data) {
    var ignoreCols = [config.name_column];
    var _cols = {};
    $.each(data.features, function(i, e) {
	$.each(e.properties, function(k, v) {
	    if (ignoreCols.indexOf(k) == -1) {
		_cols[k] = true;
	    }
	});
    });
    var cols = _.sortBy(_.keys(_cols), function(e) { return getColumnTitle(e, config); });

    var metrics = $.map(cols, function(e) {
	var meta = {column: e};
	var stats = summarizeColumn(meta, data);
	var metric = {}
	metric[stats.nonnumeric ? 'color' : 'size'] = meta;
	return metric;
    });
    // metrics may already exist if we're in debug mode
    config.metrics = (config.metrics || []).concat(metrics);
}

function summarizeColumn(meta, data) {
    // cache the computed results
    if (!meta._stats) {
	meta._stats = _summarizeColumn(meta, data);
    }
    return meta._stats;
}

// compute statistics on a given column of data for the purpose of determining
// sensible styling defaults
function _summarizeColumn(meta, data) {
    var _uniq = {};
    var sum = 0;
    var count = 0;
    var min = null;
    var max = null;
    var nonnumeric = false;

    $.each(data.features, function(i, e) {
	var val = getPropValue(e.properties, meta);
	if (isNull(val)) {
	    return;
	}

	count++;
	_uniq[val] = true;
	if (isNumeric(val)) {
	    val = +val;
	    sum += val;
	    min = (min == null ? val : Math.min(min, val));
	    max = (max == null ? val : Math.max(max, val));
	} else {
	    nonnumeric = true;
	}
    });
    var uniq = [];
    $.each(_uniq, function(k, v) {
	uniq.push(k);
    });
    uniq.sort();

    return {
	distinct: uniq,
	mean: (count > 0 ? sum / count : null),
	min: min,
	max: max,
	nonnumeric: nonnumeric,
    };
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

