
// generate a uuid of 'len' hex characters
function uuid(len) {
    var s = '';
    for (var i = 0; i < len; i++) {
	s += Math.floor(16 * Math.random()).toString(16);
    }
    return s;
}

// build a test case object from a template
function make_test_case(type, name, properties, links) {
    properties = properties || {};
    links = links || {};

    var c = {
	case_id: 'case-' + uuid(8),
	closed: false,
	date_closed: null,
	date_modified: '2012-04-05T19:00:49Z',
	domain: 'test',
	indices: {},
	properties: {
	    case_name: name,
	    case_type: type,
	    date_opened: '2012-04-05T19:00:49Z',
	    external_id: null,
	    owner_id: 'chw-c1c85473'
	},
	server_date_modified: '2012-04-05T23:00:50Z',
	server_date_opened: '2012-04-05T23:00:50Z',
	user_id: 'chw-c1c85473',
	version: '2.0',
	xform_ids: []
    }

    $.each(properties, function(k, v) {
	    c.properties[k] = v;
	});
    $.each(links, function(k, linked_case) {
	    c.indices[k] = {case_type: linked_case.properties.case_type, case_id: linked_case.case_id};
	});

    return c;
}

// build our corpus of testing data
function gen_test_data() {
    test_cases = [];

    var households = {
	drew: '41.63 -72.59',
	archibald: '42.4 -71.1',
	mortimer: '41.17 -71.59',
	noloc: null,
    };

    var pregnancies = {
        lucy: {mother_age: 22, gestational_age: 35, household: 'drew'},
        dorcas: {mother_age: 27, gestational_age: 135, household: 'drew'},
        persephone: {mother_age: 35, gestational_age: 235, household: 'mortimer'},
    };

    var children = {
	a: {gender: 'm', happiness: 2, household: 'drew'},
	b: {gender: 'f', happiness: 1, household: 'drew'},
	c: {gender: 'f', happiness: 3, household: 'drew'},
	d: {gender: 'f', happiness: 5, household: 'drew'},
	e: {gender: 'f', happiness: 4, household: 'drew'},
	f: {gender: 'f', happiness: 2, household: 'drew'},
	g: {gender: 'f', happiness: 2, household: 'drew'},
	h: {gender: 'm', happiness: 2, household: 'drew'},
	i: {gender: 'f', happiness: 4, household: 'archibald'},
	j: {gender: 'm', happiness: 2, household: 'archibald'},
	k: {gender: 'm', happiness: 5, household: 'archibald'},
    };




    var household_cases = {};
    $.each(households, function(k, v) {
	    var props = {
		geo: v,
		salary: 1e5 * Math.random(),
		dwelling: ['hut', 'apt', 'mansion'][Math.floor(Math.random() * 3)],
	    };

	    var c = make_test_case('household', k, props);
	    household_cases[k] = c;
	    test_cases.push(c);
	});

    var preg_cases = {};
    $.each(pregnancies, function(k, v) {
	    var link = {household: household_cases[v.household]};
	    delete v.household;
	    var c = make_test_case('preg', k, v, link);
	    preg_cases[k] = c;
	    test_cases.push(c);
	});

    var child_cases = {};
    $.each(children, function(k, v) {
	    var link = {household: household_cases[v.household]};
	    delete v.household;
	    var c = make_test_case('child', k, v, link);
	    child_cases[k] = c;
	    test_cases.push(c);
	});

    return test_cases;
}

function gen_test_config() {
    return {
       "case_types": [
           {
               "case_type": "household",
               "display_name": "Household",
               "geo_field": "geo",
               "fields": [
                   {
                       "field": "salary",
                       "display_name": "Annual Salary",
                       "type": "numeric"
                   },
                   {
                       "field": "dwelling",
                       "display_name": "Dwelling Type",
                       "type": "enum",
                       "values": [
                           {
                               "value": "hut"
                           },
                           {
                               "value": "apt",
                               "label": "apartment"
                           },
                           {
                               "value": "mansion"
                           }
                       ]
                   }
               ]
           },
           {
               "case_type": "preg",
               "display_name": "Pregnancy",
               "geo_linked_to": "household",
               "fields": [
                   {
                       "field": "_count",
                       "display_name": "Pregnancies per household",
                       "scale": 3,
                       "color": "#fff"
                   },
                   {
                       "field": "mother_age",
                       "display_name": "Mother's Age",
                       "type": "numeric",
                       "scale": 40
                   },
                   {
                       "field": "gestational_age",
                       "display_name": "Gestational Age (days)",
                       "type": "numeric",
                       "scale": 280,
                       "color": "#ff5"
                   }
               ]
           },
           {
               "case_type": "child",
               "display_name": "Under 5",
               "geo_linked_to": "household",
               "fields": [
                   {
                       "field": "_count",
                       "display_name": "# U5 children"
                   },
                   {
                       "field": "gender",
                       "display_name": "Gender",
                       "type": "enum",
                       "values": [
                           {
                               "value": "m",
                               "label": "male",
                               "color": "#aaf"
                           },
                           {
                               "value": "f",
                               "label": "female",
                               "color": "#faa"
                           }
                       ]
                   },
                   {
                       "field": "happiness",
                       "display_name": "Developmental Index",
                       "type": "num_discrete",
                       "scale": 5,
                       "values": [
                           {
                               "value": "1"
                           },
                           {
                               "value": "2"
                           },
                           {
                               "value": "3"
                           },
                           {
                               "value": "4"
                           },
                           {
                               "value": "5"
                           }
                       ]
                   }
               ]
           }
       ]
   };
}






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

// a custom gmaps marker where a canvas _is_ the marker itself
CanvasMarker = function(opts) {
    this.setValues(opts);

    this.$div = $('<div />');
    this.div_ = this.$div[0];
};
CanvasMarker.prototype = new google.maps.OverlayView();
CanvasMarker.prototype.onAdd = function() {
    this.$canvas = make_canvas(this.width, this.height);
    this.$div.append(this.$canvas);

    this.renderer = this.render_factory(canvas_context(this.$canvas[0]), this.width, this.height);
    this.renderer.oncreate();

    var pane = this.getPanes().overlayImage;
    $(pane).append(this.$div);
};
CanvasMarker.prototype.onRemove = function() {
    this.renderer.ondestroy();
};
CanvasMarker.prototype.draw = function() {
    this.$div.css('display', 'block');
    this.$div.css('position', 'absolute');

    var pos = this.getProjection().fromLatLngToDivPixel(this.position);
    this.$div.css('left', (pos.x - this.width / 2) + "px");
    this.$div.css('top', (pos.y - this.height / 2) + "px");
};






// initialize the google map pane
function init_map($div, default_pos, default_zoom, default_map_type) {
    var map = new google.maps.Map($div[0], {
            center: new google.maps.LatLng(default_pos[0], default_pos[1]),
            zoom: default_zoom,
            mapTypeId: {
                terrain: google.maps.MapTypeId.TERRAIN
            }[default_map_type],
	    scaleControl: true,
        });
    return map;
}

function fit_all(map, cases) {
    var bounds = new google.maps.LatLngBounds();
    var any = false;
    $.each(cases, function(id, c) {
	    if (c.marker) {
		bounds.extend(c.marker.position);
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
    var config = case_type_config(c.type()) || {};

    var geo_field = config.geo_field;
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
    return new google.maps.LatLng(lat, lon);
}

// create a marker corresponding to a (geo-enabled) case
function geoify_case(c, geo_field, map, make_marker, make_info) {
    var pos = parse_pos(c.prop(geo_field));
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


function maps_init(config, case_api_url) {
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

    if (!debug_mode) {
	$.get(case_api_url, null, function(data) {
		init_callback(map, data);
	    }, 'json');
    } else {
	var test_cases = gen_test_data();
	console.log('test data', test_cases);
	init_callback(map, test_cases);
    }
}

function init_callback(map, case_list) {
    cases = {};
    $.each(case_list, function(i, c) {
	    cases[c.case_id] = annotate(c);
	});
    $.each(cases, function(id, c) {
	    init_case(c, cases, map);
        });

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
	style: null,
    };

    var $panel = $('#panel');
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

    console.log(context);
    console.log(data);

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
	explodepie: function(cfg) { return new ExplodedPieMarkerStyle({radius: 18}, cfg); },
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
    }

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

    if (has_legend) {
	console.log('legendary!');
    }
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
	tally: TallyMetric,
    }[type];
    return new metric_factory();
}

function CountMetric() {
    this.summarize = function(v) {
	return v.length;
    }

    this.overview = function(v) {
	return new MaxMetric().summarize(v);
    }
}

function SumMetric() {
    this.summarize = function(v) {
	var k = 0;
	$.each(v, function(i, e) {
		k += e;
	    });
	return k;
    }

    this.overview = function(v) {
	return new MaxMetric().summarize(v);
    }
}

function MinMetric() {
    this.summarize = function(v) {
	var k = null;
	$.each(v, function(i, e) {
		k = (k == null ? e : Math.min(k, e));
	    });
	return k;
    }

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
    }

    this.overview = function(v) {
	return new MaxMetric().summarize(v);
    }
}

function AvgMetric() {
    this.summarize = function(v) {
	var count = new CountMetric().summarize(v);
	return (count == 0 ? null : (new SumMetric().summarize(v)) / count);
    }

    this.overview = function(v) {
	return new MaxMetric().summarize(v);
    }
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
    }

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
    }
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
	}

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
    }
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




