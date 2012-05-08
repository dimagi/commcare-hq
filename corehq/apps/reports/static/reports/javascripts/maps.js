
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
    TEST_CASES = [];

    var households = {
	drew: '41.63 -72.59',
	archibald: '42.4 -71.1',
	mortimer: '41.17 -71.59',
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
	    };

	    var c = make_test_case('household', k, props);
	    household_cases[k] = c;
	    TEST_CASES.push(c);
	});

    var preg_cases = {};
    $.each(pregnancies, function(k, v) {
	    var link = {household: household_cases[v.household]};
	    delete v.household;
	    var c = make_test_case('preg', k, v, link);
	    preg_cases[k] = c;
	    TEST_CASES.push(c);
	});

    var child_cases = {};
    $.each(children, function(k, v) {
	    var link = {household: household_cases[v.household]};
	    delete v.household;
	    var c = make_test_case('child', k, v, link);
	    child_cases[k] = c;
	    TEST_CASES.push(c);
	});

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
            }[default_map_type]
        });
    return map;
}

function fit_all(map, cases) {
    var bounds = new google.maps.LatLngBounds();
    $.each(cases, function(id, c) {
	    if (c.marker) {
		bounds.extend(c.marker.position);
	    }
        });
    map.fitBounds(bounds);
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
    var geo_field = CONFIG.geo_cases[c.type()];
    if (geo_field) {
	// create map marker associated with case

	// these are just defaults for now
	var marker_factory = function(p, m) {
	    return static_marker(p, m, case_no_data());
	};
	var info_factory = function(c) {
	    var info = $('<p>this is <span id="name"></span></p>');
	    info.find('#name').text(c.prop('case_name'));
	    return info;
	};

	geoify_case(c, geo_field, map,
		    marker_factory,
		    info_factory
		    );
    } else {
	// link this case to a geo-enabled case
	c.geo_link = search_for_geo(c, cases);
    }
}
    
// create a marker corresponding to a (geo-enabled) case
function geoify_case(c, geo_field, map, make_marker, make_info) {
    var loc = c.prop(geo_field).split(' ');
    var pos = new google.maps.LatLng(loc[0], loc[1]);
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

function search_for_geo(c, cases) {
    var geo_case = null;
    $.each(c.indices, function(k, v) {
	    var linked_id = v.case_id;
	    var linked_case = cases[linked_id];
	    if (linked_case.geo()) {
		found = linked_case.geo();
	    } else {
		found = search_for_geo(linked_case, cases);
	    }
	    if (found) {
		geo_case = found;
		return false;
	    }
	});
    return geo_case;
}






CONFIG = {
    geo_cases: {
	household: 'geo',
    },
    fields: {
	household: ['salary'],
	preg: ['#', 'mother_age', 'gestational_age'],
	child: ['#', 'gender', 'happiness'],
    },
    links_to: {
	preg: 'household',
	child: 'household',
    },
};

function maps_init(case_api_url) {
    var map = init_map($('#map'), [30., 0.], 2, 'terrain');

    /*
    $.get(case_api_url, null, function(data) {
	    init_callback(map, data);
	}, 'json');
    */

    // load testing data
    gen_test_data();
    console.log(TEST_CASES);
    init_callback(map, TEST_CASES);
}

function init_callback(map, case_list) {
    debugBulkUp(case_list, 0, 5);

    cases = {};
    $.each(case_list, function(i, c) {
	    cases[c.case_id] = annotate(c);
	});
    $.each(cases, function(id, c) {
	    init_case(c, cases, map);
        });

    fit_all(map, cases);

    // num visits is a meta-field?

    // pick an aggregation mode
    // pick a marker style

    // todo: subfilter (e.g., just male, just female)
    // what about: date ranges, filter by chw, etc.

    // marker style renders marker, and legend

    var report_context = {
	type: null,
	field: null,
	metric: null,
	style: null,
    };

    var $panel = $('#panel');
    $panel.css('text-align', 'left');
    $.each(CONFIG.fields, function(k, v) {
	    var $hdr = $('<h3 />');
	    $hdr.text(k);
	    $panel.append($hdr);
	    $.each(v, function(i, e) {
		    var $f = $('<div />');
		    $f.text(e);
		    $panel.append($f);
		    $f.click(function() {
			    report_context.type = k;
			    report_context.field = e;

			    highlight($f, '#panel div');

			    display_metric(report_context, cases);
			});
		});
	});

    $.each($('#agg div'), function(i, e) {
	    var $e = $(e);
	    $e.click(function() {
		    var metric_factory = {
			'count': CountMetric,
			'sum': SumMetric,
			'min': MinMetric,
			'max': MaxMetric,
			'avg': AvgMetric,
			'tally': TallyMetric,
		    }[$e.attr('type')];

		    report_context.metric = new metric_factory();

		    highlight($e, '#agg div');

		    display_metric(report_context, cases);
		});
	});

    $.each($('#style div'), function(i, e) {
	    var $e = $(e);
	    $e.click(function() {
		    var style = {
			'gauge': new GaugeMarkerStyle({radius: 10}),
			'intens': new IntensityMarkerStyle({radius: 10}),
			'blob': new BlobMarkerStyle({ref_radius: 15}),
			'pie': new PieMarkerStyle({radius: 13}),
			'varpie': new PieMarkerStyle({radius: 18, varsize: true}),
			'explodepie': new ExplodedPieMarkerStyle({radius: 24}),
		    }[$e.attr('type')];

		    report_context.style = style;

		    highlight($e, '#style div');

		    display_metric(report_context, cases);
		});
	});

}

function highlight($current, all) {
    $(all).css('font-weight', 'normal');
    $current.css('font-weight', 'bold');
}

function DataAggregation(cases, case_type, field, metric) {
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

    $.each(this.values, function(k, v) {
	    var result = metric.summarize(v);
	    agg.results[k] = result;
	    agg._results.push(result);
	});
    this.context = metric.overview(this._results);

    // we want something analagous to a 'left join', so we can display some kind
    // of 'null' marker for geocases without data
    // but, we can't reliably determine what case type that should be!
    var default_geo_type = CONFIG.links_to[case_type];
    if (default_geo_type) {
	$.each(cases, function(id, c) {
		if (c.type() == default_geo_type) {
		    if (!agg.results[c.id()]) {
			agg.geocases[c.id()] = c;
			agg.results[c.id()] = null;
		    }
		}
	    });
    }
}

function display_metric(context, cases) {
    var data = new DataAggregation(cases, context.type, context.field, context.metric);

    console.log(context);
    console.log(data);

    render_data(data, context.style);
    hide_nonrelevant(data, cases);

    // need to assign colors and such
    // each summation method needs a class - includes legends and such
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
}

function GaugeMarkerStyle(params) {
    this.radius = params.radius;
    this.color = params.color || 'rgb(0,255,0)';
    this.bgcolor = params.bgcolor || 'rgb(50,50,50)';

    this.get_dim = function(data, context) {
	return 2 * this.radius + 5;
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

	var pct = data / context;

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

function IntensityMarkerStyle(params) {
    this.radius = params.radius;
    this.color = params.color || 'rgb(0,255,0)';
    this.bgcolor = params.bgcolor || 'rgb(50,50,50)';

    this.get_dim = function(data, context) {
	return 2 * this.radius + 5;
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
	var pct = data / context;

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

function BlobMarkerStyle(params) {
    this.ref_radius = params.ref_radius;
    this.color = params.color || 'rgb(0,255,0)';

    this.radius = function(data, context) {
	return this.ref_radius * Math.sqrt(data / context);
    }

    this.get_dim = function(data, context) {
	return 2 * this.radius(data, context) + 5;
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

	circle();
	ctx.fillStyle = this.color;
	ctx.fill();

	circle();
	ctx.strokeStyle = 'rgb(0, 0, 0)';
	ctx.lineWidth = 2;
	ctx.stroke();
    }
}

function PieMarkerStyle(params) {
    this.ref_radius = params.radius;
    this.colors = params.colors || {};
    this.varsize = params.varsize;

    this.sum = function(data) {
	var sum = 0;
	$.each(data, function(k, v) {
		sum += v;
	    });
	return sum;
    }

    this.radius = function(data, context) {
	return this.ref_radius * (this.varsize ? Math.sqrt(this.sum(data) / context.maxsum) : 1.);
    }

    this.get_dim = function(data, context) {
	return 2 * this.radius(data, context) + 5;
    }

    this.color_for = function(k) {
	if (!this.colors[k]) {
	    this.colors[k] = randcolor();
	}
	return this.colors[k];
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
	$.each(data, function(k, v) {
		slice(0., j);
		ctx.fillStyle = mst.color_for(k);
		ctx.fill();
		j -= v / sum;
	    });

	circle();
	ctx.strokeStyle = 'rgb(0, 0, 0)';
	ctx.lineWidth = 2;
	ctx.stroke();
    }
}

function ExplodedPieMarkerStyle(params) {
    this.ref_radius = params.radius;
    this.colors = params.colors || {};
    this.offset = (params.offset != null ? params.offset : 5);

    this.radius = function(data, context) {
	return this.ref_radius * Math.sqrt(data / context.maxval);
    }

    this.get_dim = function(data, context) {
	return 2 * (this.radius(context.maxval, context) + this.offset) + 5;
    }

    this.color_for = function(k) {
	if (!this.colors[k]) {
	    this.colors[k] = randcolor();
	}
	return this.colors[k];
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

	$.each(context.vals, function(i, e) {
		slice(theta(i), theta(i + 1), mst.radius(data[e], context));
		ctx.strokeStyle = 'rgb(0, 0, 0)';
		ctx.lineWidth = 3;
		ctx.stroke();
		i += 1;
	    });

	$.each(context.vals, function(i, e) {
		slice(theta(i), theta(i + 1), mst.radius(data[e], context));
		ctx.fillStyle = mst.color_for(e);
		ctx.fill();		
		i += 1;
	    });
    }
}

function render_data(data, style) {
    $.each(data.results, function(k, v) {
	    var c = data.geocases[k];
	    c.marker.setIcon(v != null ? new Marker(style).render(v, data.context) : case_no_data());
	    c.display(true);
	});
}

function hide_nonrelevant(data, cases) {
    $.each(cases, function(id, c) {
	    if (data.geocases[id] == null) {
		(c.display || function(x){})(false);
	    }
	});
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
	return (new SumMetric().summarize(v)) / (new CountMetric().summarize(v));
    }

    this.overview = function(v) {
	return new MaxMetric().summarize(v);
    }
}

function TallyMetric() {
    this.summarize = function(v) {
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
    return render_marker(gauge(0.), 18, 18);
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





function debugBulkUp(cases, mult, dispersion) {
    var init_num = cases.length;
    var dispersion = 5.;
    for (var i = 0; i < init_num; i++) {
	for (var j = 0; j < mult; j++) {
	    var c = $.extend(true, {}, cases[i]);
	    var loc = c.properties.geo.split(' ');
	    loc[0] = +loc[0] + dispersion * (2. * Math.random() - 1.);
	    loc[1] = +loc[1] + dispersion * (2. * Math.random() - 1.);
	    c.properties.geo = loc[0] + ' ' + loc[1];
	    cases.push(c);
	}
    }
}
