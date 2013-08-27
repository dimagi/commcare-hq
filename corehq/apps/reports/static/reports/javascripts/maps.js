


function mapsInit(context) {
    var map = initMap($('#map'), [30., 0.], 2, 'Map');
    initData(context.data, context.config);
    initMetrics(map, context.data, context.config);
    $('#fit').click(function() { zoomToAll(map); });
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

    L.control.scale().addTo(map);

    return map;
}

function initData(data, config) {
    $.each(data.features, function(i, e) {
	// pre-cache popup detail
	e.popupContent = formatDetailPopup(e, config);
    });
}

function initMetrics(map, data, config) {
    var render = function(metric) {
	loadData(map, data, makeDisplayContext(metric));
    };

    $.each(config.metrics, function(i, e) {
	var $e = $('<div></div>');
	$e.addClass('choice');
	$e.text(e.title);
	$e.click(function() {
	    $('#sidebar div').removeClass('selected');
	    $e.addClass('selected');
	    render(e);
	});
	$('#sidebar').append($e);
    });

    // load markers and set initial viewport
    render(null);
    zoomToAll(map);
}

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

DEFAULT_SIZE = 10;
DEFAULT_MIN_SIZE = 3;
DEFAULT_COLOR = 'rgba(255, 120, 0, .7)';

function makeDisplayContext(metric) {
    var getValue = function(props, meta) {
	var val = props[meta.column];
	if (meta.thresholds) {
	    // TODO error if val is not numeric
	    val = matchThresholds(val, meta.thresholds);
	}
	return val;
    }

    var getSize = function(props) {
	var meta = metric.size;

	if (meta == null) {
	    return DEFAULT_SIZE;
	} else if (isNumeric(meta)) {
	    return meta;
	} else {
	    var val = getValue(props, meta);
	    if (!isNumeric(val)) {
		return null;
	    }

	    var rad = DEFAULT_SIZE * Math.sqrt(val / meta.baseline);
	    rad = Math.min(Math.max(rad, meta.min || DEFAULT_MIN_SIZE), meta.max || 9999);
	    return rad;
	}
    }

    var getColor = function(props) {
	var meta = metric.color;

	var c = $.Color((function() {
	    if (meta == null) {
		return DEFAULT_COLOR;
	    } else if (typeof meta == 'string') {
		return meta;
	    } else {
		var val = getValue(props, meta);
		if (meta.categories) {
		    return matchCategories(val, meta.categories); //TODO no match
		} else {
		    return matchSpline(val, meta.colorstops, blendColor);
		}
	    }
	})());
	return {color: c.toHexString(), alpha: c.alpha()};
    }

    return {
	pointToLayer: function (feature, latlng) {
	    if (metric == null) {
		return L.marker(latlng);
	    }

	    var size = getSize(feature.properties);
	    if (size == null) {
		//error; TODO handle
	    }

	    var fill = getColor(feature.properties);
	    if (fill == null) {
		//error; TODO handle
	    }

            return L.circleMarker(latlng, {
		color: "#000",
		weight: 1,
		opacity: 1,
		radius: size,
		fillColor: fill.color,
		fillOpacity: fill.alpha
	    });
	},
	onEachFeature: function(feature, layer) {
            layer.bindPopup(feature.popupContent);
	}
    }
}

function formatDetailPopup(feature, config) {
    var TEMPLATE = [
	'<h3>{{ name }}</h3>',
	'<hr>',
	'<table>',
	'{{#each detail}}<tr><td>{{ label }}</td><td style="font-weight: bold; text-align: right; padding-left: 20px;">{{ value }}</td></tr>{{/each}}',
	'</table>',
    ].join('\n');

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





function isNumeric(x) {
    return (x != null && x != '' && !isNaN(+x));
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
// 'categories' may define a mapping for '_other', which will be user for
// all values that do not have an explicit value assigned
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

// factory function to generate a traditional gmaps marker
function static_marker(pos, map, icon) {
    return new google.maps.Marker({position: pos, icon: icon, map: map});
}



// initialize the google map pane

function fit_all(map, cases) {
    var bounds = new google.maps.LatLngBounds();
    var any = false;
    $.each(cases, function(id, c) {
            if (c.marker) {
                bounds.extend(c.marker.position);

		// ugly
		if (!window.MARKERS) {
		    MARKERS = [];
		}
		MARKERS.push(c.marker);

                any = true;
            }
        });
    if (any) {
        map.fitBounds(bounds);
    } else {
        alert("This domain has no geo-referenced cases!");
    }
}

function annotate(c) {
    c.id = function() {
        return c.case_id;
    }
    c.type = function() {
        return c.properties.case_type;
    }
    c.prop = function(k) {
        return c.properties[k];
    }
    c.geo = function() {
        return (c.marker ? c : c.geo_link);
    }
    c.datum = function(field) {
        if (field == '#') {
            return {};
        } else {
            return c.prop(field);
        }
    }
    return c;
}

// take a raw case object and annotate with various methods
function init_case(c, cases, map) {
    var config = case_type_config(c.type()) || null;
    if (config === null) {
        return;
    }
    var geo_field = config.geo_field;
    if (!geo_field && !config.geo_linked_to) {
        geo_field = '_loc';
    }
    if (geo_field) {
        // create map marker associated with case

        // these are just defaults for now
        var marker_factory = function(p, m) {
            return static_marker(p, m, case_no_data());
        };
        var info_factory = function(c) {
            var info = $('<p>This is <span id="type"></span> case "<span id="name"></span>"</p>');
            info.find('#name').text(c.prop('case_name'));
            info.find('#type').text(c.type());
            return info;
        };

        geoify_case(c, geo_field, map,
                    marker_factory,
                    info_factory
                    );
    } else {
        // link this case to a geo-enabled case
        c.geo_link = search_for_geo(c, config.geo_linked_to, cases);
    }
}

function parse_pos(raw) {
    var loc = ('' + raw).split(' ');
    var lat = +loc[0];
    var lon = +loc[1];
    if (isNaN(lat) || isNaN(lon)) {
        return null;
    }
    return [lat, lon];
}

function case_to_pos(c, geo_field) {
    var pos;
    if (geo_field == '_loc') {
        var loc = c.prop('linked_location');
        var lat = loc.latitude;
        var lon = loc.longitude;
        if (lat != null && lon != null) {
            pos = [+lat, +lon];
	}
    } else {
        pos = parse_pos(c.prop(geo_field));
    }
    return (pos ? new google.maps.LatLng(pos[0], pos[1]) : null);
}

// create a marker corresponding to a (geo-enabled) case
function geoify_case(c, geo_field, map, make_marker, make_info) {
    var pos = case_to_pos(c, geo_field);
    if (pos == null) {
        return;
    }
    var marker = make_marker(pos, map);
 
    if (make_info) {
        var infocontent = make_info(c);
        marker.infowindow = new google.maps.InfoWindow({content: infocontent[0]});
    }

    google.maps.event.addDomListener(marker.div_ || marker, 'click', function(event) {
            //if (LAST_MARKER != null) {
            //    LAST_MARKER.infowindow.close();
            //}
            marker.infowindow.open(map, marker);
            //LAST_MARKER = marker;
        });

    c.marker = marker;
    c.display = function(show) {
        c.marker.setMap(show ? map : null);
    }
}

function search_for_geo(c, link_type, cases) {
    var geo_case = null;
    $.each(c.indices, function(k, v) {
            var linked_id = v.case_id;
            var linked_case = cases[linked_id];
            if (linked_case.geo() && linked_case.type() == link_type) {
                found = linked_case.geo();
            } else {
                found = search_for_geo(linked_case, link_type, cases);
            }
            if (found) {
                geo_case = found;
                return false;
            }
        });
    return geo_case;
}

function lookup_by(list, field, val) {
    var match = null;
    $.each(list, function(i, e) {
            if (e[field] == val) {
                match = e;
                return false;
            }
        });
    return match;
}

function case_type_config(case_type) {
    return lookup_by(CONFIG, 'case_type', case_type);
}

function field_config(case_type, field) {
    return lookup_by(case_type_config(case_type).fields, 'field', field);
}

function field_type(fc) {
    if (fc.field == '_count') {
        return 'count';
    } else {
        return fc.type;
    }
}


function maps_init(config) {
    var debug_mode = (window.location.href.indexOf('?debug=true') != -1);
    if (debug_mode) {
        config = gen_test_config();
    }

    if (config == null) {
        alert('This domain is not configured for maps reports');
    }
    // set to global var for now
    CONFIG = config.case_types;

    var map = init_map($('#map'), [30., 0.], 2, 'terrain');
    return map;
}

function maps_refresh(map, cases) {
    var debug_mode = (window.location.href.indexOf('?debug=true') != -1);
    if (debug_mode) {
        cases = gen_test_data();
    }
    init_callback(map, cases, CONFIG);
}


function topological_sort(dag) {
    var ordered_nodes = [];
    var done = false;

    var all_referred_to = {};
    $.each(dag, function(k, v) {
        all_referred_to[v] = true;
    });

    while (!done) {
        var referred_to = {};
        var empty = true;
        $.each(dag, function(k, v) {
            referred_to[v] = true;
            empty = false;
        });
        if (empty) {
            done = true;
            break;
        }

        var unreferenced = {};
        $.each(dag, function(k, v) {
            if (!referred_to[k]) {
                unreferenced[k] = true;
            }
        });

        $.each(unreferenced, function(k, v) {
            ordered_nodes.push(k);
            delete dag[k];
        });
    }

    $.each(all_referred_to, function(k, v) {
        if (ordered_nodes.indexOf(k) == -1) {
            ordered_nodes.push(k);
        }
    });

    ordered_nodes.reverse();
    return ordered_nodes;
}

function init_callback(map, case_list) {
    cases = {};
    $.each(case_list, function(i, c) {
            cases[c.case_id] = annotate(c);
        });

    // need to process cases in a certain order, so that 'root' cases are geo-enabled before the cases
    // that may link to them
    var case_type_dag = {};
    $.each(CONFIG, function(i, e) {
        if (e.geo_linked_to) {
            case_type_dag[e.case_type] = e.geo_linked_to;
        }
    });
    var case_types = topological_sort(case_type_dag);
    var _cases = _.sortBy(case_list, function(e) { return case_types.indexOf(e.type()); });
    $.each(_cases, function(i, c) {
        init_case(c, cases, map);
    });

    for (var i = 0; i < (window.MARKERS || []).length; i++) {
	MARKERS[i].setMap(null);
    }
    fit_all(map, cases);

    // num visits is a meta-field?

    // todo: subfilter (e.g., just male, just female)
    // what about: date ranges, filter by chw, etc.

    // marker style renders marker, and legend

    var report_context = {
        cases: cases,
        case_type: null,
        field: null,
        metric: null,
        style: null
    };

    var $panel = $('#panel');
    $panel.empty();
    $.each(CONFIG, function(i, c) {
            var $hdr = $('<h3 />');
            $hdr.text(c.display_name || c.case_type);
            $panel.append($hdr);
            $.each(c.fields, function(i, f) {
                    var $f = $('<div />');
                    $f.addClass('choice');
                    $f.text(f.display_name || f.field);
                    $panel.append($f);
                    $f.click(function() {
                            select_field(c.case_type, f, report_context, $f);
                            display_metric(report_context);
                        });
                });
        });
    $('#sidebar').show();

    $.each($('#agg span'), function(i, e) {
            var $e = $(e);
            $e.addClass('choice');
            $e.click(function() {
                    if ($e.hasClass('disabled')) {
                        return;
                    }

                    select_metric($e.attr('type'), report_context, $e);
                    display_metric(report_context);
                });
        });

    $.each($('#style span'), function(i, e) {
            var $e = $(e);
            $e.addClass('choice');
            $e.click(function() {
                    if ($e.hasClass('disabled')) {
                        return;
                    }

                    select_style($e.attr('type'), report_context, $e);
                    display_metric(report_context);
                });
        });

}

function select_field(case_type, field, report_context, $field) {
    report_context.case_type = case_type;
    report_context.field = field;

    highlight($field, '#panel div');

    $('#agg').show();
    set_metrics_for_field(report_context);
}

function set_metrics_for_field(report_context) {
    var ftype = field_type(report_context.field);
    var cmult = case_type_config(report_context.case_type).geo_linked_to != null;

    var allowed_metrics = [];
    if (cmult) {
        allowed_metrics.push('count');
    }
    if (ftype == 'numeric' || ftype == 'num_discrete') {
        if (cmult) {
            allowed_metrics.push('sum');
            allowed_metrics.push('min');
            allowed_metrics.push('max');
            allowed_metrics.push('avg');
        } else {
            allowed_metrics.push('val');
        }
    }
    if (ftype == 'num_discrete' || ftype == 'enum') {
        allowed_metrics.push('tally');
    }

    $('#agg span').addClass('disabled');
    $.each(allowed_metrics, function(i, e) {
            $('#agg span[type="' + e + '"]').removeClass('disabled');
        });

    var metric = report_context.metric;
    if (allowed_metrics.length == 1 && allowed_metrics[0] != report_context.metric) {
        metric = allowed_metrics[0];
    } else if (report_context.metric != null && allowed_metrics.indexOf(report_context.metric) == -1) {
        metric = null;
    }
    select_metric(metric, report_context);
}

function select_metric(metric, report_context, $metric) {
    $metric = $metric || $('#agg span[type="' + metric + '"]');

    report_context.metric = metric;

    highlight($metric, '#agg span');

    if (metric) {
        $('#style').show();
        set_styles_for_metric(report_context);
    } else {
        $('#style').hide();
    }
}

function set_styles_for_metric(report_context) {
    var cmult = case_type_config(report_context.case_type).geo_linked_to != null;

    var allowed_styles = [];
    if (report_context.metric != 'tally') {
        allowed_styles.push('gauge');
        allowed_styles.push('intens');
        allowed_styles.push('blob');
    } else {
        if (cmult) {
            allowed_styles.push('pie');
            allowed_styles.push('varpie');
            allowed_styles.push('explodepie');
        } else {
            allowed_styles.push('dot');
        }
    }

    $('#style span').addClass('disabled');
    $.each(allowed_styles, function(i, e) {
            $('#style span[type="' + e + '"]').removeClass('disabled');
        });

    if (allowed_styles.length == 1 && allowed_styles[0] != report_context.style) {
        select_style(allowed_styles[0], report_context);
    } else if (report_context.style != null && allowed_styles.indexOf(report_context.style) == -1) {
        select_style(null, report_context);
    }
}

function select_style(style, report_context, $style) {
    $style = $style || $('#style span[type="' + style + '"]');

    report_context.style = style;

    highlight($style, '#style span');
}

function highlight($current, all) {
    $(all).removeClass('selected');
    if ($current) {
        $current.addClass('selected');
    }
}

function DataAggregation(cases, case_type, field, metric_type) {
    this.geocases = {};
    this.values = {};
    this.results = {};
    this._results = [];

    var agg = this;
    $.each(cases, function(id, c) {
            if (c.type() != case_type) {
                return;
            }

            var geo = c.geo();
            if (!geo) {
                return;
            }

            var geo_id = geo.id();
            agg.geocases[geo_id] = geo;
            if (!agg.values[geo_id]) {
                agg.values[geo_id] = [];
            }
            var val = c.datum(field);
            agg.values[geo_id].push(val);
        });

    // fill in empty entries of the geocases that have no linked data cases
    var default_geo_type = case_type_config(case_type).geo_linked_to;
    if (default_geo_type) {
        $.each(cases, function(id, c) {
                if (c.type() == default_geo_type && c.geo()) {
                    if (!agg.values[c.id()]) {
                        agg.geocases[c.id()] = c;
                        agg.values[c.id()] = [];
                    }
                }
            });
    }

    if (metric_type != null) {
        var metric = make_metric(metric_type);
        $.each(this.values, function(k, v) {
                var result = metric.summarize(v);
                agg.results[k] = result;
                if (result != null) {
                    agg._results.push(result);
                }
            });
        this.context = metric.overview(this._results);
    } else {
        $.each(this.values, function(k, v) {
                agg.results[k] = null;
            });
    }

}

function display_metric(context) {
    var data = new DataAggregation(context.cases, context.case_type, context.field.field, context.metric);

    render_data(data, context.style, context.field);
    hide_nonrelevant(data, context.cases);
}

function make_style(type, config) {
    var factory = {
        gauge:      function(cfg) { return new GaugeMarkerStyle({radius: 10}, cfg); },
        intens:     function(cfg) { return new IntensityMarkerStyle({radius: 10}, cfg); },
        blob:       function(cfg) { return new BlobMarkerStyle({ref_radius: 15}, cfg); },
        dot:        function(cfg) { return new PieMarkerStyle({radius: 8}, cfg); },
        pie:        function(cfg) { return new PieMarkerStyle({radius: 13}, cfg); },
        varpie:     function(cfg) { return new PieMarkerStyle({radius: 18, varsize: true}, cfg); },
        explodepie: function(cfg) { return new ExplodedPieMarkerStyle({radius: 18}, cfg); }
    }[type];
    return factory(config);
}

function Marker(style) {
    this.style = style;

    this.render = function(data, context) {
        var dim = this.style.get_dim(data, context);
        if (!dim.w) {
            dim = {w: dim, h: dim};
        }

        var m = this;
        return render_marker(function(ctx, w, h) { m.style.draw(data, context, ctx, w, h); }, dim.w, dim.h);
    };

    this.legend = function(context, $div) {
        if (style.legend && context) {
            style.legend(context, $div);
            return true;
        } else {
            return false;
        }
    }
}

function GaugeMarkerStyle(params, config) {
    this.radius = params.radius;
    this.scale = config.scale;
    this.color = config.color || 'rgb(0,255,0)';
    this.bgcolor = params.bgcolor || 'rgb(50,50,50)';

    this.get_dim = function(data, context) {
        return 2 * this.radius + 5;
    }

    this.get_max = function(context) {
        return this.scale || context || 1.;
    }

    this.draw = function(data, context, ctx, w, h) {
        var mst = this;
        var arc = function(a, b) {
            ctx.arc(.5 * w, .5 * h, mst.radius, a * Math.PI*2, b * Math.PI*2); 
        }
        var circle = function() {
            ctx.beginPath();
            arc(0., 1.);
            ctx.closePath();
        }
        var slice = function(pct) { 
            ctx.beginPath();
            ctx.moveTo(.5 * w, .5 * h);
            arc(-.25, Math.min(pct, 0.9999) - .25); 
            ctx.lineTo(.5 * w, .5 * h);
            ctx.closePath();
        }

        var pct = data / this.get_max(context);

        circle();
        ctx.fillStyle = this.bgcolor;
        ctx.fill();

        slice(pct);
        ctx.fillStyle = this.color;
        ctx.fill();

        circle();
        ctx.strokeStyle = 'rgb(0, 0, 0)';
        ctx.lineWidth = 2;
        ctx.stroke();
    }
}

function IntensityMarkerStyle(params, config) {
    this.radius = params.radius;
    this.scale = config.scale;
    this.color = config.color || 'rgb(0,255,0)';
    this.bgcolor = params.bgcolor || 'rgb(50,50,50)';

    this.get_dim = function(data, context) {
        return 2 * this.radius + 5;
    }

    this.get_max = function(context) {
        return this.scale || context || 1.;
    }

    this.draw = function(data, context, ctx, w, h) {
        var mst = this;
        var arc = function(a, b) {
            ctx.arc(.5 * w, .5 * h, mst.radius, a * Math.PI*2, b * Math.PI*2); 
        }
        var circle = function() {
            ctx.beginPath();
            arc(0., 1.);
            ctx.closePath();
        }
        var pct = data / this.get_max(context);

        circle();
        ctx.fillStyle = this.bgcolor;
        ctx.fill();

        circle();
        ctx.save();
        ctx.globalAlpha = pct;
        ctx.fillStyle = this.color;
        ctx.fill();
        ctx.restore();

        circle();
        ctx.strokeStyle = 'rgb(0, 0, 0)';
        ctx.lineWidth = 2;
        ctx.stroke();
    }
}

function BlobMarkerStyle(params, config) {
    this.ref_radius = params.ref_radius;
    this.min_radius = params.min_radius || 3;
    this.scale = config.scale;
    this.color = config.color || 'rgb(0,255,0)';

    this.radius = function(data, context) {
        return Math.max(this.ref_radius * Math.sqrt(data / this.get_max(context)), this.min_radius);
    }

    this.get_dim = function(data, context) {
        return 2 * this.radius(data, context) + 5;
    }

    this.get_max = function(context) {
        return this.scale || context || 1.;
    }

    this.draw = function(data, context, ctx, w, h) {
        var mst = this;
        var arc = function(a, b) {
            ctx.arc(.5 * w, .5 * h, Math.max(mst.radius(data, context), mst.min_radius), a * Math.PI*2, b * Math.PI*2); 
        }
        var circle = function() {
            ctx.beginPath();
            arc(0., 1.);
            ctx.closePath();
        }

        circle();
        ctx.fillStyle = (data > 0 ? this.color : 'black');
        ctx.fill();

        circle();
        ctx.strokeStyle = 'rgb(0, 0, 0)';
        ctx.lineWidth = 2;
        ctx.stroke();
    }
}

function color_for(cfg, k) {
    if (cfg.values == null) {
        cfg.values = [];
    }

    var item = lookup_by(cfg.values, 'value', k);
    if (item == null) {
        item = {value: k};
        cfg.values.push(item);
    }

    var color = item.color;
    if (color == null) {
        color = randcolor();
        item.color = color;
    }

    return color;
}

function for_each_choice(config, data, func, reverse) {
    var vals = [];
    $.each(config.values || [], function(i, e) {
            vals.push(e.value);
        });
    $.each(data, function(k, v) {
            if (vals.indexOf(k) == -1) {
                vals.push(k);
            }
        });

    if (reverse) {
        vals.reverse();
    }

    $.each(vals, function(i, k) {
            func(k, data[k] || 0.);
        });
}

function PieMarkerStyle(params, config) {
    this.ref_radius = params.radius;
    this.config = config;
    this.varsize = params.varsize;

    this.sum = function(data) {
        var sum = 0;
        $.each(data, function(k, v) {
                sum += v;
            });
        return sum;
    }

    this.radius = function(data, context) {
        return this.ref_radius * (this.varsize ? Math.sqrt(this.sum(data) / this.get_max(context)) : 1.);
    }

    this.get_dim = function(data, context) {
        return 2 * this.radius(data, context) + 5;
    }

    this.get_max = function(context) {
        return this.config.scale || context.maxsum;
    }

    this.color_for = function(k) {
        return color_for(this.config, k);
    }

    this.draw = function(data, context, ctx, w, h) {
        var mst = this;
        var arc = function(a, b) {
            ctx.arc(.5 * w, .5 * h, mst.radius(data, context), a * Math.PI*2, b * Math.PI*2);
        }
        var circle = function() {
            ctx.beginPath();
            arc(0., 1.);
            ctx.closePath();
        }
        var slice = function(i, j) { 
            ctx.beginPath();
            ctx.moveTo(.5 * w, .5 * h);
            arc(i - .25, Math.min(j, 0.9999) - .25); 
            ctx.lineTo(.5 * w, .5 * h);
            ctx.closePath();
        }

        var sum = this.sum(data);

        var j = 1.;
        for_each_choice(this.config, data, function(k, v) {
                slice(0., j);
                ctx.fillStyle = mst.color_for(k);
                ctx.fill();
                j -= v / sum;
            }, true);

        circle();
        ctx.strokeStyle = 'rgb(0, 0, 0)';
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    this.legend = function(context, $div) {
        enum_legend(context, this.config, $div);
    }
}

function ExplodedPieMarkerStyle(params, config) {
    this.ref_radius = params.radius;
    this.config = config;
    this.offset = (params.offset != null ? params.offset : 5);

    this.get_max = function(context) {
        return this.config.scale || context.maxsum;
    }

    // how many square pixels per 1.0 of data
    this.area_per = function(context) {
        return Math.PI * Math.pow(this.ref_radius, 2.) / this.get_max(context);
    }

    // radius for N of data, factoring in size of pie slice (more choices == narrower slice)
    this.radius = function(data, context, total_uniques) {
        return Math.sqrt(this.area_per(context) * data * total_uniques / Math.PI);
    }

    this.num_choices = function(data) {
        var num = 0;
        for_each_choice(this.config, data, function(k, v) {
                num++;
            });
        return num;
    }

    this.get_dim = function(data, context) {
        return 2 * (this.radius(context.maxval, context, this.num_choices(data)) + this.offset) + 5;
    }

    this.color_for = function(k) {
        return color_for(this.config, k);
    }

    this.draw = function(data, context, ctx, w, h) {
        var mst = this;
        var arc = function(a, b, x, y, r) {
            ctx.arc(x, y, r, a * Math.PI*2, b * Math.PI*2); 
        }
        var slice = function(i, j, r) {
            var a = i - .25;
            var b =  Math.min(j, 0.9999) - .25;
 
            var theta = 2. * Math.PI * (a + b) * .5;
            var x = .5 * w + mst.offset * Math.cos(theta);
            var y = .5 * h + mst.offset * Math.sin(theta);

            ctx.beginPath();
            ctx.moveTo(x, y);
            arc(a, b, x, y, r);
            ctx.lineTo(x, y);
            ctx.closePath();
        }

        var i = 0;
        var theta = function(i) { return i / context.vals.length; };

        var num = this.num_choices(data);
        for_each_choice(this.config, data, function(k, v) {
                var _slice = function() {
                    slice(theta(i), theta(i + 1), mst.radius(v, context, num));
                };

                _slice();
                ctx.strokeStyle = 'rgb(0, 0, 0)';
                ctx.lineWidth = 3;
                ctx.stroke();

                _slice();
                ctx.fillStyle = mst.color_for(k);
                ctx.fill();
                
                i += 1;
            });
    }

    this.legend = function(context, $div) {
        enum_legend(context, this.config, $div);
    }
}

function render_data(data, style_type, field_config) {
    var style = null;
    if (style_type) {
        style = new Marker(make_style(style_type, field_config));
    }

    var renderer = function(v, context) {
        return (v != null && style != null ? style.render(v, context) : case_no_data());
    };

    $.each(data.results, function(k, v) {
            var c = data.geocases[k];
            c.marker.setIcon(renderer(v, data.context));
            c.display(true);
        });
    
    render_legend(style, data.context);
}

function render_legend(style, context) {
    $('#legend-inner').empty();
    var has_legend = (style != null ? style.legend(context, $('#legend-inner')) : false);
    $('#legend')[has_legend ? 'show' : 'hide']();
}

function hide_nonrelevant(data, cases) {
    $.each(cases, function(id, c) {
            if (data.geocases[id] == null) {
                (c.display || function(x){})(false);
            }
        });
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

function make_metric(type) {
    var metric_factory = {
        count: CountMetric,
        val: MaxMetric, // guaranteed to have only 1 item in dataset
        sum: SumMetric,
        min: MinMetric,
        max: MaxMetric,
        avg: AvgMetric,
        tally: TallyMetric
    }[type];
    return new metric_factory();
}

function CountMetric() {
    this.summarize = function(v) {
        return v.length;
    };

    this.overview = function(v) {
        return new MaxMetric().summarize(v);
    };
}

function SumMetric() {
    this.summarize = function(v) {
        var k = 0;
        $.each(v, function(i, e) {
                k += e;
            });
        return k;
    };

    this.overview = function(v) {
        return new MaxMetric().summarize(v);
    };
}

function MinMetric() {
    this.summarize = function(v) {
        var k = null;
        $.each(v, function(i, e) {
                k = (k == null ? e : Math.min(k, e));
            });
        return k;
    };

    this.overview = function(v) {
        return new MaxMetric().summarize(v);
    }
}

function MaxMetric() {
    this.summarize = function(v) {
        var k = null;
        $.each(v, function(i, e) {
                k = (k == null ? e : Math.max(k, e));
            });
        return k;
    };

    this.overview = function(v) {
        return new MaxMetric().summarize(v);
    };
}

function AvgMetric() {
    this.summarize = function(v) {
        var count = new CountMetric().summarize(v);
        return (count == 0 ? null : (new SumMetric().summarize(v)) / count);
    };

    this.overview = function(v) {
        return new MaxMetric().summarize(v);
    };
}

function TallyMetric() {
    this.summarize = function(v) {
        if (v.length == 0) {
            return null;
        }

        var k = {};
        $.each(v, function(i, e) {
                if (k[e] == null) {
                    k[e] = 0;
                }
                k[e]++;
            });
        return k;
    };

    this.overview = function(v) {
        var maxes = [];
        var sums = [];
        var uniques = [];
        $.each(v, function(i, e) {
                var vals = [];
                $.each(e, function(k, v) {
                        if (uniques.indexOf(k) == -1) {
                            uniques.push(k);
                        }
                        vals.push(v);
                    });
                maxes.push(new MaxMetric().summarize(vals));
                sums.push(new SumMetric().summarize(vals));
            });

        return {vals: uniques, maxval: new MaxMetric().summarize(maxes), maxsum: new MaxMetric().summarize(sums)};
    };
}






function case_no_data() {
    return render_marker(function(ctx, w, h) {
            var arc = function(a, b) {
                ctx.beginPath();
                ctx.arc(.5*w, .5*h, .3*Math.min(w, h), a * 2*Math.PI, b * 2*Math.PI);
                //ctx.closePath();
            }

            arc(0., 1.);
            ctx.strokeStyle = 'rgba(128, 0, 0, .3)';
            ctx.lineWidth = 6;
            ctx.stroke();

            for (var i = 0; i < 3; i++) {
                arc(.3333 * i, .3333 * (i + .75));
                ctx.strokeStyle = 'rgba(255, 0, 0, .8)';
                ctx.lineWidth = 3;
                ctx.stroke();
            }
        }, 18, 18);
}


function AnimMarker(ctx, w, h) {
    this.ctx = ctx;
    this.w = w;
    this.h = h;
    this.anim = null;

    this.oncreate = function() {
        /*
        var t0 = new Date().getTime();
        var c1 = randcolor();
        var c2 = randcolor();
        var c3 = randcolor();
        var period = 4 * Math.random() + 2.;

        var mkr = this;
        var draw = function() {
            var clock = ((new Date().getTime()) - t0) / 1000.;
            this.ctx.clear();
            drawpie(mkr.ctx, mkr.w, mkr.h, (clock % period) / period, c1, c2, c3);
        }

        draw();
        this.anim = setInterval(draw, 30);
        */

        var m = this;
        this.redraw = function(k) { drawpie(m.ctx, m.w, m.h * (.2 + .008*k), .005*k, 'rgb(50,50,50)', 'rgb(0,255,0)', 'rgb(0,0,0)'); };

        this.setTo(0.);
    }

    this.ondestroy = function() {
        //clearInterval(this.anim);
    }

    this.setTo = function(k) {
        this.k = k;
        this.ctx.clear();
        this.redraw(k);
    }

    this.transitionTo = function(k, period, tag, easing) {
        var FRAME_LENGTH = 30;

        tag = tag || k;
        easing = easing || trig_easing;

        if (this.anim != null) {
            if (this.anim.tag == tag) {
                return;
            }
            clearInterval(this.anim.timer);
        }

        var t0 = new Date().getTime();
        var k0 = this.k;

        var m = this;
        var animate = function() {
            var clock = ((new Date().getTime()) - t0) / 1000.;
            if (clock > period || k == m.k) {
                m.setTo(k);
                clearInterval(m.anim.timer);
                m.anim = null;
                return;
            }

            m.setTo(k0 + (k - k0) * easing(clock / period));
        };

        var timer = setInterval(animate, FRAME_LENGTH);
        this.anim = {tag: tag, timer: timer};
    }
}
      
function trig_easing(x) {
    return 0.5 * (Math.sin((x - .5) * Math.PI) + 1);
}

function linear_easing(x) {
    return x;
}

function biyeun_progress_bar_easing(x) {
    return x + .66 * Math.sin(x * Math.PI) / Math.PI * Math.sin(3 * 2 * Math.PI * x);
}




function randcolor(min, max) {
    min = min || 0.;
    max = max || 1.;

    var k = function() {
        return Math.round(255 * Math.pow((max - min) * Math.random() + min, 1/2.2));
    };
    return 'rgb(' + k() + ',' + k() + ',' + k() + ')';
};

function drawpie(ctx, width, height, phase, c1, c2, c3) {
    phase = phase || 1.;
    c1 = c1 || randcolor();
    c2 = c2 || randcolor();
    c3 = c3 || randcolor();

    if (phase < .5) {
        var _ = c1;
        c1 = c2;
        c2 = _;
    }
    phase = (phase * 2) % 1.;

    var arc = function(a, b) {
        ctx.arc(.5 * width, .5 * height, .5 * .8 * Math.min(width, height), a * Math.PI*2, b * Math.PI*2, true); 
    }

    ctx.beginPath();
    arc(0., 1.);
    ctx.closePath();
    ctx.fillStyle = c1;
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(.5 * width, .5 * height);
    arc(-.25, phase - .25); 
    ctx.lineTo(.5 * width, .5 * height);
    ctx.closePath();
    ctx.fillStyle = c2;
    ctx.fill();

    ctx.beginPath();
    arc(0., 1.);
    ctx.closePath();
    ctx.strokeStyle = c3;
    ctx.lineWidth = 2;
    ctx.stroke();
}

function gauge(k) {
    return function(c,w,h) { drawpie(c,w,h, .005*k, 'rgb(50,50,50)', 'rgb(0,255,0)', 'rgb(0,0,0)'); };
}

