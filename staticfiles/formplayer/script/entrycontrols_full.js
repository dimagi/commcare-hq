/* === INHERITANCE PATTERN === */

function inherit (subclass, superclass) {
  subclass._super = superclass._super || {};
  for (var e in superclass) {
    if (e != '_super' && e != 'super') {
      if (typeof(superclass[e]) != 'function') {
        subclass[e] = superclass[e];
      } else {
        if (subclass._super[e] == null) {
          subclass._super[e] = [];
        }
        subclass._super[e].push(superclass[e]);
        subclass[e] = passToParent(e);
      }
    }
  }
  subclass.super = function (funcName) {
    return invokeSuper(this, funcName);
  }
}

function passToParent (funcName) {
  return function () {
    return this.super(funcName).apply(null, arguments);
  }
}

function invokeSuper (self, funcName) {
  return function () {
    var basefunc = self._super[funcName].pop();
    if (!basefunc) {
      throw new Error('function ' + funcName + ' not defined in superclass');
    }
    var retval = basefunc.apply(self, arguments);
    self._super[funcName].push(basefunc);
    return retval;
  }
}

/* TO USE:
 *
 * early in the constructor of the child class, call:
 *   inherit(this, new SuperClass(...));
 * this is akin to calling super(...); inside a java constructor
 *
 * this call will load all variables and functions from the parent class
 * into this class.
 *
 * add additional variables and methods after the inherit() call. to
 * overload a method in the parent class, simply redefine the function
 * in this class
 *
 * to call a parent method explicitly, do:
 *   this.super('someMethod')(args);
 * this is akin to calling super.someMethod(args); in java
 */

/* ============================= */


function Entry () {
  this.help = function () {
    showError(activeQuestion["help"] || "There is no help text for this question.");
  }

  this.clear = function () {
    this.setAnswer(null, true);
  }
}

function SimpleEntry () {
  inherit(this, new Entry());

  this.shortcuts = [];

  this.prevalidate = function (q) {
    return true;
  }

  this.destroy = function () {
    for (var i = 0; i < this.shortcuts.length; i++) {
      shortcut.remove(this.shortcuts[i]);
    }
  }

  this.add_shortcut = function (hotkey, func) {
    set_shortcut(hotkey, func);
    this.shortcuts.push(hotkey);
  }
}

function InfoEntry () {
  inherit(this, new SimpleEntry());

  this.getAnswer = function () {
    return null;
  }

  this.load = function (q, $container) {
    //not needed
  }
}

function UnsupportedEntry (datatype) {
  inherit(this, new SimpleEntry());

  this.answer = null;

  this.getAnswer = function () {
    return this.answer;
  }

  //just spit back the answer that was originally set
  this.setAnswer = function (ans) {
    this.answer = ans;
  }

  this.load = function (q, $container) {
    $container.html('<div class="unsupported">Sorry, web entry cannot support this type of question <nobr>(' + (datatype == 'unrecognized' ? 'unknown type' : datatype) + ')</nobr></div>');
  }
}

function FreeTextEntry (args) {
  inherit(this, new SimpleEntry());

  args = args || {};
  this.domain = args.domain || 'full';
  this.length_limit = args.length_limit || 500;
  this.textarea = args.prose;

  this.inputfield = null;
  this.default_answer = null;

  this.load = function (q, $container) {
    this.mkWidget(q, $container);

    this.setAnswer(this.default_answer);
  }

  this.mkWidget = function (q, $container) {
    if (!this.textarea) {
      $container.html('<input id="textfield" maxlength="' + this.length_limit + '" type="text" style="width: ' + this.widgetWidth() + '" /><span id="type" style="margin-left: 15px; font-size: x-small; font-style: italic; color: grey;">(' + this.domainText() + ')</span>');
      var widget = $container.find('#textfield');
    } else {
      $container.html('<textarea id="textarea" style="width: 33em; height: 10em; font-family: sans-serif;"></textarea>');
      var widget = $container.find('#textarea');

      /*
      var type_newline = function() {
        //TODO: doesn't work in chrome
        var evt = document.createEvent("KeyboardEvent");
        evt.initKeyEvent("keypress", true, true, window,
                         0, 0, 0, 0,
                         13, 0); 
        widget[0].dispatchEvent(evt);
      }

      this.add_shortcut('ctrl+enter', type_newline);
      this.add_shortcut('shift+enter', type_newline);
      this.add_shortcut('alt+enter', type_newline);
      */
    }
    //widget.focus();
    this.inputfield = widget[0];
    widget.change(function() { q.onchange(); });
  }

  this.getControl = function () {
    return this.inputfield;
  }

  this.getRaw = function () {
    var control = this.getControl();
    return (control != null ? control.value : null);
  }

  this.getAnswer = function () {
    var raw = $.trim(this.getRaw());
    return (raw == '' ? null : raw);
  }

  this.setAnswer = function (answer, postLoad) {
    var control = this.getControl();
    if (control) {
      control.value = (answer != null ? answer : '');
    } else {
      this.default_answer = answer;
    }
  }

  this.prevalidate = function (q) {
    var raw = this.getRaw();
    if (raw) {
      var errmsg = this._prevalidate(raw);
      if (errmsg) {
        q.showError(errmsg);
        return false;
      }
    }
    return true;
  }

  this._prevalidate = function (raw) {
    return null;
  }

  this.domainText = function() {
    return 'free-text';
  }

  this.widgetWidth = function() {
    return '20em';
  }
}

function PasswordEntry (args) {
  args.length_limit = args.length_limit || 9;
  inherit(this, new FreeTextEntry(args));

  this.mkWidget = function () {
    $('#answer')[0].innerHTML = '<input id="textfield" maxlength="' + this.length_limit + '" type="passwd"/>';
    this.inputfield = $('#textfield')[0];
  }
}

function IntEntry (parent, length_limit) {
  inherit(this, new FreeTextEntry({parent: parent, domain: 'numeric', length_limit: length_limit || 9}));

  this.getAnswer = function () {
    var val = this.super('getAnswer')();
    return (val != null ? +val : val);
  }

  this._prevalidate = function(raw) {
    return (isNaN(+raw) || +raw != Math.floor(+raw) ? "Not a valid whole number" : null);
  }

  this.domainText = function() {
    return 'numeric';
  }

  this.widgetWidth = function() {
    return '8em';
  }
}

function FloatEntry (parent) {
  inherit(this, new FreeTextEntry({parent: parent}));

  this.getAnswer = function () {
    var val = this.super('getAnswer')();
    return (val != null ? +val : val);
  }

  this._prevalidate = function (raw) {
    return (isNaN(+raw) ? "Not a valid number" : null);
  }

  this.domainText = function() {
    return 'decimal';
  }

  this.widgetWidth = function() {
    return '8em';
  }
}

function MultiSelectEntry (args) {
  inherit(this, new SimpleEntry());

  this.choices = args.choices;
  this.choicevals = args.choicevals;
  this.layout_override = args.layout_override;
  this.as_single = (args.meta || {}).as_single;

  this.isMulti = true;
  //this.buttons = null;
  this.default_selections = null;

  this.$container = null;

  this.init_vals = function () {
    if (this.choicevals == null && typeof this.choices[0] == 'object') {
      this.choicevals = [];
      for (var i = 0; i < this.choices.length; i++) {
        var choice = this.choices[i];
        this.choices[i] = choice.lab;
        this.choicevals.push(choice.val);
      }
    }
  }
  this.init_vals();

  this.load = function (q, $container) {
    this.$container = $container;
    this.group = 'sel-' + nonce();

    for (var i = 0; i < this.choices.length; i++) {
      var label = (i < 10 ? '' + ((i + 1) % 10) : (i < 36 ? 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[i - 10] : null));

      var $choice = $('<div><span id="num"></span> <input id="ch-' + i + '" type="' + (this.isMulti ? 'checkbox' : 'radio') + '" /> <span id="label"></span></div>');
      $choice.find('#num').text(label + ')');
      $choice.find('#num').hide();
      $choice.find('#label').text(this.choices[i]);
      var $inp = $choice.find('input');
      $inp.attr('name', this.group);
      $inp.attr('value', i);
      $choice.addClass('sel');

      $choice.click((function($inp) {
          return function(ev) {
            if (ev.target != $inp[0]) {
              $inp.click();
              $inp.change(); //appears the simulated click() doesn't trigger this?
            }
          }
        })($inp));

      //this.add_shortcut(label, this.selectFunc(i));
      $container.append($choice);
    }
    $container.append('<div id="clear_"><a id="clear" href="#">clear</a></div>');
    //$('#ch-0').focus();

    //var self = this;
    //this.add_shortcut('up', function() { self.scroll(false); });
    //this.add_shortcut('down', function() { self.scroll(true); });

    this.initted = true;

    this.setAnswer(this.default_selections);

    var ctrl = this;
    $container.find('input').change(function() {
        ctrl.pendchange(q, !ctrl.isMulti);
      });

    $container.find('#clear').click(function () {
        $container.find('input').removeAttr('checked');
        ctrl.pendchange(q, true);
        return false;
      });
  }

  this.COMMIT_DELAY = 300; //ms
  this.pendchange = function(q, immed) {
    if (this.timer) {
      clearTimeout(this.timer);
    }
    this.timer = setTimeout(function() { q.onchange(); }, immed ? 0 : this.COMMIT_DELAY);
  }

  this.getAnswer = function () {
    var selected = [];
    for (i = 0; i < this.choices.length; i++) {
      if (this.choiceWidget(i, true).checked) {
        selected.push(this.valAt(i));
      }
    }
    return selected;
  }

  this.valAt = function (i) {
    return (this.choicevals != null ? this.choicevals[i] : i + 1);
  }

  //answer is null or list
  this.setAnswer = function (answer, postLoad) {
    if (this.initted) {
      for (var i = 0; i < this.choices.length; i++) {
        var button = this.choiceWidget(i, true);
        var checked = (answer != null && answer.indexOf(this.valAt(i)) != -1);
        button.checked = checked;
        if (checked) {
          //  this.choiceWidget(i).focus();
        }
      }
    } else {
      this.default_selections = answer;
    }
  }

  this.selectFunc = function (i) {
    var self = this;
    return function () {
      var cbox = this.choiceWidget(i); //is 'this' a bug? (used for keyboard shortcuts?)
      if (cbox.is(':checked')) {
        cbox.removeAttr('checked');
      } else {
        cbox.attr('checked', true);
      }
      cbox.focus();
    }
  }

  this.scroll = function (dir) {
    var checkboxes = [];
    for (var i = 0; i < this.choices.length; i++) {
      checkboxes.push(this.choiceWidget(i, true));
    }
    var focussed = $(':focus');
    var activeIx = -1;
    for (var i = 0; i < focussed.length; i++) {
      var ix = checkboxes.indexOf(focussed[i]);
      if (ix != -1) {
        activeIx = ix;
        break;
      }
    }
    if (activeIx >= 0) {
      var newIx = (activeIx + this.choices.length + (dir ? 1 : -1)) % this.choices.length;
      this.focus(newIx);
    }
  }

  this.focus = function(i) {
    this.choiceWidget(i).focus();
  }

  this.choiceWidget = function(i, dom) {
    var elem = this.$container.find('#ch-' + i);
    return (dom ? elem[0] : elem);
  }
}

function SingleSelectEntry (args) {
  inherit(this, new MultiSelectEntry(args));

  this.isMulti = false;

  this.getAnswer = function () {
    var selected = this.super('getAnswer')();
    return selected.length > 0 ? selected[0] : null;
  }

  this.setAnswer = function (answer, postLoad) {
    if (this.initted) {
      this.super('setAnswer')(answer != null ? [answer] : null, postLoad);
    } else {
      this.default_selections = answer;
    }
  }

  this.selectFunc = function (i) {
    var self = this;
    return function () {
      var cbox = this.choiceWidget(i); //is 'this' a bug? (used for keyboard shortcuts?)
      cbox.attr('checked', true);
      //      cbox.focus();
    }
  }
}

/*
function clearButtons (buttons, except_for) {
  for (var i = 0; i < buttons.length; i++) {
    if (buttons[i] != except_for) {
      buttons[i].resetStatus();
    }
  }
}
*/

function DateEntry (args) {
  inherit(this, new SimpleEntry());

  this.format = 'mm/dd/yy';

  this.$picker = null;

  this.load = function (q, $container) {
    this.widget_id = 'datepicker-' + nonce();
    $container.html('<input id="' + this.widget_id + '" type="text"><span id="type" style="margin-left: 15px; font-size: x-small; font-style: italic; color: grey;">(' + this.format.replace('yy', 'yyyy') + ')</span>');
    this.$picker = $container.find('#' + this.widget_id);
    var nextYear = new Date().getFullYear() + 1;
    this.$picker.datepicker({
        changeMonth: true,
        changeYear: true,
        dateFormat: this.format,
        yearRange: "" + (nextYear - 100) + ":" + nextYear
    });

    this.initted = true;

    this.setAnswer(this.def_ans);

    this.$picker.change(function() { q.onchange(); });
  }

  this.setAnswer = function (answer, postLoad) {
    if (this.initted) {
      this.$picker.datepicker('setDate', answer ? $.datepicker.parseDate('yy-mm-dd', answer) : null);
      this.ans = answer;
    } else {
      this.def_ans = answer;
    }

  }

  this.getAnswer = function () {
    var raw = this.$picker.datepicker('getDate');
    return (raw != null ? $.datepicker.formatDate('yy-mm-dd', raw) : null);
  }

}

function TimeOfDayEntry (parent) {
  inherit(this, new FreeTextEntry({parent: parent, length_limit: 5}));

  this.getAnswer = function () {
    var val = this.super('getAnswer')();
    var t = this.parseAnswer(val);
    if (t != null) {
      return intpad(t.h, 2) + ':' + intpad(t.m, 2);
    } else {
      return null;
    }
  }

  this._prevalidate = function (raw) {
    var t = this.parseAnswer($.trim(raw));
    if (t == null || t.h < 0 || t.h >= 24 || t.m < 0 || t.m >= 60) {
      return "Not a valid time (00:00\u201423:59)";
    } else {
      return null;
    }
  }

  this.parseAnswer = function (answer) {
    var match = /^([0-9]{1,2})\:([0-9]{2})$/.exec(answer);
    if (!match) {
      return null;
    } else {
      return {h: +match[1], m: +match[2]};
    }
  }

  this.domainText = function() {
    return 'hh:mm, 24-hour clock';
  }

  this.widgetWidth = function() {
    return '5em';
  }
}

function GeoPointEntry () {
  inherit(this, new SimpleEntry());

  this.timers = {};
  this.DEFAULT = {lat: 30., lon: 0., zoom: 1, anszoom: 6};

  this.load = function (q, $container) {
    this.mkWidget(q, $container);
    this.setAnswer(this.default_answer, true);

    this.commit = function() {
      q.onchange();
    }
  }

  this.mkWidget = function (q, $container) {
    var crosshairs = 'iVBORw0KGgoAAAANSUhEUgAAABMAAAATCAQAAADYWf5HAAAACXZwQWcAAAATAAAAEwDxf4yuAAAAAmJLR0QAAKqNIzIAAAAJcEhZcwAAAEgAAABIAEbJaz4AAAAySURBVCjPY2hgIAZiCPwHAyKUMQxbZf9RAHKwIMSg+hEQqhtJBK6MKNNGTvCSld6wQwBd8RoA55WDIgAAAABJRU5ErkJggg==';
    var crosshair_size = 19;
    $container.html('<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td id="lat"></td><td id="lon"></td><td align="right" valign="bottom"><a id="clear" href="#">clear</a></td></tr></table><div id="map"></div><div><form><input id="query"><input type="submit" id="search" value="Search"></form></div>');
    var $map = $container.find('#map');
    // TODO: dynamic sizing
    var W = 400; 
    var H = 250;
    $map.css('width', W+'px');
    $map.css('height', H+'px');

    $map.css('background', '#eee');

    var $wait = $('<div />');
    $wait.css('margin', 'auto');
    $wait.css('padding-top', '60px');
    $wait.css('max-width', '200px');
    $wait.css('color', '#bbb');
    $wait.css('font-size', '24pt');
    $wait.css('line-height', '28pt');
    $wait.text('please wait while the map loads...');
    $map.append($wait);

    this.lat = null;
    this.lon = null;
    this.$lat = $container.find('#lat');
    this.$lon = $container.find('#lon');
    $.each([this.$lat, this.$lon], function(i, $e) {
        $e.css('font-weight', 'bold');
        $e.css('width', '8em');
      });

    var widget = this;
    $container.find('#clear').click(function () {
	widget.set_latlon(null, null);
	widget.commit();
        return false;
      });

    this.$query = $container.find('#query');
    this.$query.css('width', '80%');
    this.$search = $container.find('#search');
    this.$search.css('width', '15%');
    this.$search.click(function() {
        q = widget.$query.val().trim();
	if (q) {
          widget.search(q);
        }
	return false;
      });

    var on_gmap_load = function() {
	$map.empty();
	widget.map = new google.maps.Map($map[0], {
		mapTypeId: google.maps.MapTypeId.ROADMAP,
		center: new google.maps.LatLng(widget.DEFAULT.lat, widget.DEFAULT.lon),
		zoom: widget.DEFAULT.zoom
	    });

	widget.geocoder = new google.maps.Geocoder();

	google.maps.event.addListener(widget.map, "center_changed", function() { widget.update_center(); });

	$ch = $('<img src="data:image/png;base64,' + crosshairs + '">');
	$ch.css('position', 'relative')
	$ch.css('top', ((H/*$map.height()*/ - crosshair_size) / 2) + 'px');
	$ch.css('left', ((W/*$map.width()*/ - crosshair_size) / 2) + 'px');
	$ch.css('z-index', '500');
	$map.append($ch);
    };

    var GMAPS_API = 'http://maps.googleapis.com/maps/api/js?key=' + GMAPS_API_KEY + '&sensor=false';
    if (typeof google == "undefined") {
	_GMAPS_INIT = on_gmap_load
        $.getScript(GMAPS_API + '&callback=_GMAPS_INIT');
    } else {
	on_gmap_load();
    }

  }

  this.getAnswer = function () {
    return (this.lat != null ? [this.lat, this.lon] : null);
  }

  this.setAnswer = function (answer, postLoad) {
    if (postLoad) {
      if (answer) {
        this.set_latlon(answer[0], answer[1]);
        this.map.setCenter(new google.maps.LatLng(answer[0], answer[1]));
	this.map.setZoom(this.DEFAULT.anszoom);
      } else {
        this.set_latlon(null, null);
      }
    } else {
      this.default_answer = answer;
    }
  }

  this.update_center = function() {
    var center = this.map.getCenter();
    var lat = center.lat();
    var lon = center.lng();

    if (this.set_latlon(lat, lon)) {
      var widget = this;
      this.delay_action('move', function() { widget.commit(); }, 1.);
    }
  }

  this.set_latlon = function(lat, lon) {
    lon = lon % 360.;
    if (lon < 0) {
      lon += 360.
    }
    lon = lon % 360.;
    if (lon >= 180.) {
      lon -= 360.;
    }

    if (lat == this.lat && lon == this.lon) {
      return false;
    }

    this.lat = lat;
    this.lon = lon;

    this.$lat.text(lat != null ? (lat >= 0. ? 'N' : 'S') + intpad(Math.abs(lat).toFixed(5), 8) : '??.?????');
    this.$lon.text(lat != null ? (lon >= 0. ? 'E' : 'W') + intpad(Math.abs(lon).toFixed(5), 9) : '???.?????');

    return true;
  }

  this.delay_action = function(tag, dofunc, delay) {
    var timer = this.timers[tag];
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    this.timers[tag] = setTimeout(dofunc, 1000 * delay);
  }

  this.search = function(query) {
    var map = this.map;
    this.geocoder.geocode({'address': query}, function(results, status) {
      if (status == google.maps.GeocoderStatus.OK) {
        map.fitBounds(results[0].geometry.viewport);
        map.setCenter(results[0].geometry.location);
      }
    });
  }
}

function renderQuestion (q, $container, init_answer) {
  var control = null;

  q.domain_meta = q.domain_meta || {};

  if (q.customlayout != null) {
    control = q.customlayout();
  } else if (q.datatype == "str") {
    control = new FreeTextEntry({domain: q.domain, prose: q.domain_meta.longtext});
  } else if (q.datatype == "int") {
    control = new IntEntry();
  } else if (q.datatype == "longint") {
    control = new IntEntry(null, 15);
  } else if (q.datatype == "float") {
    control = new FloatEntry();
  //  } else if (q.datatype == "passwd") {
  //control = new PasswordEntry({domain: q.domain});
  } else if (q.datatype == "select") {
    control = new SingleSelectEntry({choices: q.choices, choicevals: q.choicevals});
  } else if (q.datatype == "multiselect") {
    control = new MultiSelectEntry({choices: q.choices, choicevals: q.choicevals, meta: q.domain_meta});
  } else if (q.datatype == "date") {
    control = new DateEntry(q.domain_meta);
  } else if (q.datatype == "time") {
    control = new TimeOfDayEntry();
  } else if (q.datatype == "geo") {
    control = new GeoPointEntry();
  } else {
    control = new UnsupportedEntry(q.datatype);
  }

  if (control == null) {
    console.log('no active control');
    return null;
  }

  control.setAnswer(init_answer);
  control.load(q, $container);
  return control;
}

function nonce() {
  return Math.floor(Math.random()*1e9);
}

function intpad (x, n) {
  var s = x + '';
  while (s.length < n) {
    s = '0' + s;
  }
  return s;
}
