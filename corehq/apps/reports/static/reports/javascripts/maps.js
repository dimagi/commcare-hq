



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

function fit_all(map, markers) {
    var bounds = new google.maps.LatLngBounds();
    $.each(markers, function(i, marker) {
            bounds.extend(marker.position);
        });
    map.fitBounds(bounds);
}

// create a marker corresponding to a (geo-enabled) case
function geo_case(case_, map, make_marker, make_info) {
    var pos = new google.maps.LatLng(case_.loc[0], case_.loc[1]);
    var marker = make_marker(pos, map);
 
    if (make_info) {
        var infocontent = make_info(case_);
        marker.infowindow = new google.maps.InfoWindow({content: infocontent[0]});
    }

    google.maps.event.addDomListener(marker.div_ || marker, 'click', function(event) {
            //if (LAST_MARKER != null) {
            //    LAST_MARKER.infowindow.close();
            //}
            marker.infowindow.open(map, marker);
            //LAST_MARKER = marker;
        });

    return marker;
}

// factory function to generate a traditional gmaps marker
function static_marker(pos, map, icon) {
    return new google.maps.Marker({position: pos, icon: icon, map: map});
}







function maps_init() {

    var map = init_map($('#map'), [30., 0.], 2, 'terrain');

    var MARKER_MODE = 3;

    var gauge = function(k) {
	return function(c,w,h) { drawpie(c,w,h, .005*k, 'rgb(50,50,50)', 'rgb(0,255,0)', 'rgb(0,0,0)'); };
    }

    var markers = [];
    $.each(DATA, function(i, case_) {
            switch (MARKER_MODE) {
            case 1: var marker_factory = static_marker; break;
            case 2: var marker_factory = function(p, m) {
                    return static_marker(p, m, render_marker(gauge(0.), 24, 24));
                };
                break;
            case 3: var marker_factory = function(p, m) {
                    return new CanvasMarker({
                            position: p,
                            map: m,
                            width: 33, height: 33,
                            render_factory: function(c, w, h) { return new AnimMarker(c, w, h); }
                        });
                }
                break;
            }

            var marker = geo_case(case_, map,
                marker_factory,
                function(c) {
                    var info = $('<p>this is <span id="name"></span></p>');
                    info.find('#name').text(c.name);
                    return info;
                }
            );
	    case_.marker = marker;
            markers.push(marker);
        });
          
    fit_all(map, markers);

    var $panel = $('#panel');
    $.each(['A', 'B', 'C'], function(i, e) {
	    $x = $('<div></div>');
	    $x.text('factor ' + e);
	    $panel.append($x);
	    $x.click(function() {
		    /*
		    $.each(markers, function(i, m) {
			    m.setIcon(render_marker(gauge(DATA[i][e]), 24, 24));
			});
		    */
		    $.each(DATA, function(i, c) {
			    c.marker.renderer.setTo(c[e]);
			});
		});
	});

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

	this.setK(0.);
    }

    this.ondestroy = function() {
        //clearInterval(this.anim);
    }

    this.setK = function(k) {
	this.k = k;
	this.ctx.clear();
	drawpie(this.ctx, this.w, this.h, .005*k, 'rgb(50,50,50)', 'rgb(0,255,0)', 'rgb(0,0,0)');
    }

    this.setTo = function(k) {
	if (this.anim != null) {
	    clearInterval(this.anim);
	}

	var period = 0.75;
        var t0 = new Date().getTime();
	var k0 = this.k;

	var m = this;
	var doit = function() {
            var clock = ((new Date().getTime()) - t0) / 1000.;
	    if (clock > period || k == m.k) {
		m.setK(k);
		clearInterval(m.anim);
		m.anim = null;
		return;
	    }

	    m.setK(k0 + (k - k0) * 0.5 * (Math.sin((clock / period - .5) * Math.PI) + 1));
	}

	this.anim = setInterval(doit, 30);
    }
}
      






function randcolor(min, max) {
    min = min || 0.;
    max = max || 1.;

    var k = function() {
        return Math.round(255 * ((max - min) * Math.random() + min));
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

