
// a map control map that lists the various display metrics for this report
// and allows you to select and display them
MetricsControl = L.Control.extend({
    options: {
        position: 'bottomleft'
    },

    onAdd: function(map) {
	this.$div = $('#metrics');
	this.div = this.$div[0];
        L.DomEvent.disableClickPropagation(this.div);
	this.$div.show();
	return this.div;
    },

    // TODO support an explicit 'show just markers again' option

    addMetric: function(metric) {
	var $e = $('<div></div>');
	$e.addClass('choice');
	$e.text(metric.title);
	var m = this;
	$e.click(function() {
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
	    attribution: 'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery &copy; <a href="http://mapbox.com">MapBox</a>',
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
    $.each(data.features, function(i, e) {
	// pre-cache popup detail
	e.popupContent = formatDetailPopup(e, config);
    });
}

// set up the configured display metrics
function initMetrics(map, data, config) {
    $.each(config.metrics, function(i, e) {
	setMetricDefaults(e, data, config);
    });

    var m = new MetricsControl({data: data}).addTo(map);

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
	map.fitBounds(map.activeOverlay.getBounds());
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

	// scale value with area of marker
	var rad = DEFAULT_SIZE * Math.sqrt(val / meta.baseline);
	rad = Math.min(Math.max(rad, meta.min || DEFAULT_MIN_SIZE), meta.max || 9999);
	return rad;
    }
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
	    if (isNull(val)) {
		return null;
	    }

	    if (meta.categories) {
		return matchCategories(val, meta.categories);
	    } else {
		if (!isNumeric(val)) {
		    throw new TypeError('numeric value required [' + val + ']');
		}
		return matchSpline(val, meta.colorstops, blendColor);
	    }
	}
    })();
    if (c == null) {
	return null;
    }

    c = $.Color(c);
    return {color: c.toHexString(), alpha: c.alpha()};
}

DEFAULT_ICON_URL = 'http://mrgris.com/dimagispace/media/jonvik_dance.gif';
function getIcon(meta, props) {
    //TODO support css sprites
    var icon = (function() {
	if (typeof meta == 'string') {
	    return meta;
	} else {
	    var val = getPropValue(props, meta);
	    if (isNull(val)) {
		return null;
	    }
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
    var DEFAULT_TEMPLATE = [
	'<h3>{{ name }}</h3>',
	'<hr>',
	'<table>',
	'{{#each detail}}<tr>',
	  '<td>{{ label }}</td>',
	  '<td style="font-weight: bold; text-align: right; padding-left: 20px;">',
	    '{{#if value}}{{ value }}{{ else }}\u2014{{/if}}',
	  '</td>',
	'</tr>{{/each}}',
	'</table>',
    ].join('\n');
    var TEMPLATE = config.detail_template || DEFAULT_TEMPLATE;

    var context = {props: feature.properties};
    if (config.name_column) {
	context.name = feature.properties[config.name_column];
    }
    context.detail = [];
    $.each(config.detail_columns, function(i, e) {
	context.detail.push({label: config.column_titles[e] || e, value: feature.properties[e]});
    });

    var template = Handlebars.compile(TEMPLATE);
    var content = template(context);
    return content;
}

// attempt to set sensible defaults for any missing parameters in the metric definitions
function setMetricDefaults(metric, data, config) {
    if (!metric.title) {
	var varcols = [];
	$.each(['size', 'color', 'icon'], function(i, e) {
	    if (typeof metric[e] == 'object' && metric[e].column) {
		var col = metric[e].column;
		if (varcols.indexOf(col) == -1) {
		    varcols.push(col);
		}
	    }
	});
	metric.title = $.map(varcols, function(e) { return config.column_titles[e] || e; }).join(' / ');
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

// compute statistics on a given column of data for the purpose of determining
// sensible styling defaults
function summarizeColumn(meta, data) {
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



function isNumeric(x) {
    return (typeof x == 'number' && !isNaN(+x));
}

function isNull(x) {
    return (x === undefined || x === null || x === '');
}



// convert a numerical value into an enumerated value based on cutoff thresholds
// 'thresholds' must be in ascending order
// e.g., thresholds of [2, 5, 10] creates 4 buckets: <2; [2, 5); [5, 10); >=10
// return the lower bound of the matching bucket, or '-' for the lowest bucket
function matchThresholds(val, thresholds) {
    var cat = '-';
    $.each(thresholds, function(i, e) {
	if (e <= val) {
	    cat = e;
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
function matchCategories(val, categories) {
    if (categories.hasOwnProperty(val)) {
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








//// OLD STUFF

// create a (hidden) canvas
function make_canvas(w, h) {
    var $canvas = $('<canvas />');
    $canvas.attr('width', w);
    $canvas.attr('height', h);
    return $canvas;
}

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





function render_legend(style, context) {
    $('#legend-inner').empty();
    var has_legend = (style != null ? style.legend(context, $('#legend-inner')) : false);
    $('#legend')[has_legend ? 'show' : 'hide']();
}

function enum_legend(context, config, $div) {
    var _data = {};
    $.each(context.vals, function(i, e) {
            _data[e] = null;
        });
    var $t = $('<table />');
    for_each_choice(config, _data, function(k, v) {
            var name = (lookup_by(config.values || [], 'value', k) || {}).label || k;
            var color = color_for(config, k);

            var $r = $('<tr>');
            var $color = $('<td>');
            $color.css('background', color);
            $color.addClass('enumlegendcolor');
            $r.append($color);
            var $label = $('<td>');
            $label.addClass('enumlegendlabel');
            $label.text(name);
            $r.append($label);
            $t.append($r);
        });
    $div.append($t);
}

function randcolor(min, max) {
    min = min || 0.;
    max = max || 1.;

    var k = function() {
        return Math.round(255 * Math.pow((max - min) * Math.random() + min, 1/2.2));
    };
    return 'rgb(' + k() + ',' + k() + ',' + k() + ')';
};

