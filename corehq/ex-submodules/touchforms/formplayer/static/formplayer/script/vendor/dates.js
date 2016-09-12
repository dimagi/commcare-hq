


monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function DateWidgetContext (args) {
  this.DEFAULT_FUTURE_RANGE = 1826; //days ~= 5 years
  //formatting constants
  this.MAX_MONTHS_FOR_YEARLESS = 8;
  this.YEAR_COLUMN = 5;
  this.NUM_DECADE_CHOICES = 10;
  this.DECADE_ROLLOVER = 4;

  this.args = args || {};
  this.textfields = make_date_fields(this);

  this.init = function (answer, dir) {
    this.setAllowedRange(this.args);
    this.setDate(answer);
    this.initScreens(dir, answer);
  }

  this.setDate = function (datestr) {
    var olddate = this.getDate();
    if (datestr == null) {
      this.year = null;
      this.month = null;
      this.day = null;
      this.prefill();
    } else {
      var parsed = parseDate(datestr);
      this.year = parsed.year;
      this.month = parsed.month;
      this.day = parsed.day;
    }
    this.year_bucket = null;
    this.changed = (olddate != null && this.getDate() != olddate);
  }

  this.setAllowedRange = function (args) {
    var setlimit = function (datelimit, limitdelta, limitdefault, assignfunc) {
      if (datelimit) {
        var datefields = parseDate(datelimit);
      } else {
        limitdelta = (limitdelta == null ? limitdefault : limitdelta);
        datelimit = new Date(new Date().getTime() + limitdelta * 86400000);
        var datefields = {
          year: datelimit.getFullYear(),
          month: datelimit.getMonth() + 1,
          day: datelimit.getDate()
        };
      }

      datefields.date = mkdate(datefields.year, datefields.month, datefields.day);
      assignfunc(datefields);
    }

    var self = this;
    setlimit(args.mindate, args.mindiff != null ? -args.mindiff : null, -50000, function (df) {
        self.minyear = df.year;
        self.minmonth = df.month;
        self.minday = df.day;
        self.mindate = df.date;
      });
    setlimit(args.maxdate, args.maxdiff, this.DEFAULT_FUTURE_RANGE, function (df) {
        self.maxyear = df.year;
        self.maxmonth = df.month;
        self.maxday = df.day;
        self.maxdate = df.date;
      });
    this.outofrangemsg = (args.outofrangemsg != null ? args.outofrangemsg + ' The allowed range is: {{range}}.' : 'This date is outside the allowed range ({{range}}).');

    if (this.mindate > this.maxdate) {
      throw new Error('bad allowed date range');
    }

    this.specificity = null;
    if (this.minyear == this.maxyear) {
      this.specificity = 'year';
      if (this.minmonth == this.maxmonth) {
        this.specificity = 'month';
        //we don't pre-fill day even if it's the only allowed date, as it makes it impossible to
        //submit a blank answer
      }
    }
  }

  this.prefill = function () {
    if (this.specificity == 'year') {
      this.year = this.minyear;
    }
    if (this.specificity == 'month') {
      this.year = this.minyear;
      this.month = this.minmonth;
    }
  }

  this.initScreens = function (dir, answer) {
    this.screens = ['day'];
    if (monthCount(this.maxyear, this.maxmonth) - monthCount(this.minyear, this.minmonth) + 1 <= this.MAX_MONTHS_FOR_YEARLESS) {
      this.screens.push('monthyear');
    } else {
      this.screens.push('month');
      this.screens.push('year');
      if (Math.floor(this.maxyear / this.YEAR_COLUMN) - Math.floor(this.minyear / this.YEAR_COLUMN) > 2) {
        this.screens.push('decade');
      }
    }

    this.screen = (dir || answer == null ? this.getFirstScreen() : this.getLastScreen());
  }

  this.isFull = function () {
    return (this.year != null && this.month != null && this.day != null);
  }

  this.isEmpty = function () {
    return (this.year_bucket == null && this.year == null && this.month == null && this.day == null);
  }

  //emptiness that factors in the pre-filling of fields for restricted input ranges
  this.isEffectivelyEmpty = function () {
    return this.isEmpty() || (!this.isFull() && !this.changed);
  }

  this.isValid = function () {
    return (this.isFull() && this.day <= daysInMonth(this.month, this.year));
  }

  this.isInRange = function () {
    if (this.isValid()) {
      return rangeOverlap(this.mindate, this.maxdate, mkdate(this.year, this.month, this.day));
    } else {
      return false;
    }
  }

  this.getDate = function () {
    if (this.isFull()) {
      return this.year + '-' + intpad(this.month, 2) + '-' + intpad(this.day, 2);
    } else {
      return null;
    }
  }

  this.refresh = function () {
    questionEntry.update(freeEntry);
    if (this.answerbar == null) {
      this.answerbar = make_date_answerbar(this.textfields);
    }
    answerBar.update(this.answerbar);

    var year_bucket = this.getYearBucket();
    if (this.year != null) {
      this.setText('y', this.year + '');
    } else if (year_bucket != null) {
      sstart = year_bucket.start + '';
      send = year_bucket.end + '';
      syear = '';
      for (i = 0; i < 4; i++) {
        if (sstart[i] == send[i]) {
          syear += sstart[i];
        } else {
          break;
        }
      }
      while (syear.length < 4) {
        syear += '\u2022';
      }
      this.setText('y', syear);
    } else {
      this.setText('y', null);
    }
    this.setText('m', this.month != null ? (numericMonths() ? intpad(this.month, 2) : monthName(this.month)) : null);
    this.setText('d', this.day != null ? intpad(this.day, 2) : null);

    if (this.screen == 'decade') {
      this.showScreen(decadeSelect(this.make_decades(), this.getChoiceVal('decade'), this));
    } else if (this.screen == 'year') {
      this.showScreen(yearSelect(this.getYearBucket(), this.year, this));
    } else if (this.screen == 'month') {
      this.showScreen(monthSelect(this.year, this.month, this));
    } else if (this.screen == 'day') {
      this.showScreen(daySelect(this.month, this.year, this.day, this));
    } else if (this.screen == 'monthyear') {
      this.showScreen(monthYearSelect(this.make_months(), this.getChoiceVal('monthyear'), this));
    }
  }

  this.setText = function (field, val) {
    this.textfields[field].setText(val);
  }

  //it's asking for trouble to set choice values to types that are not comparable (i.e., lists, dicts), so we have to map certain date fields to ints
  this.getChoiceVal = function (field) {
    if (field == 'decade') {
      var bucket = this.getYearBucket();
      return (bucket != null ? bucket.start : null);
    } else if (field == 'monthyear') {
      return monthCount(this.year, this.month);
    }
  }

  this.revChoiceVal = function (field, val) {
    if (field == 'decade') {
      var buckets = this.make_decades();
      for (var i = 0; i < buckets.length; i++) {
        if (buckets[i].start == val) {
          return buckets[i];
        }
      }
    } else if (field == 'monthyear') {
      return {y: Math.floor(val / 12), m: (val % 12) + 1};
    }
  }

  this.showScreen = function (choice_info, selected_val) {
    this.highlight();

    freeEntryKeyboard.update(choice_info.layout);

    //all below MUST come after the widget is rendered (taken care of by the line above)

    this.cur_buttons = choice_info.get_buttons();

    for (var i = 0; i < this.cur_buttons.length; i++) {
      if (choice_info.dateranges[i] != null && !rangeOverlap(this.mindate, this.maxdate, choice_info.dateranges[i].start, choice_info.dateranges[i].end)) {
        this.cur_buttons[i].setStatus('disabled');
      }
    }
  }

  this.highlight = function () {
    var self = this;
    var highlightField = function (domobj, field) {
      domobj.setBgColor(self.screensForField(field).indexOf(self.screen) != -1 ? HIGHLIGHT_COLOR : '#fff');
    }
    highlightField(this.textfields.y, 'year');
    highlightField(this.textfields.m, 'month');
    highlightField(this.textfields.d, 'day');
  }

  this.next = function () {
    var empty = this.isEffectivelyEmpty();

    if (empty || this.isFull()) {
      if (!empty && !this.isValid()) {
        showError('This is not a valid date.');
      } else if (!empty && !this.isInRange()) {
        showError(this.outofrangemsg.replace('{{range}}', readableDate(this.minyear, this.minmonth, this.minday) + ' \u2014 ' + readableDate(this.maxyear, this.maxmonth, this.maxday)));
      } else {
        answerQuestion();
      }
    } else {
      currentScreenUnchosen = true;
      for (i = 0; i < this.cur_buttons.length; i++) {
        if (this.cur_buttons[i].status == 'selected') {
          currentScreenUnchosen = false;
          break;
        }
      }
      
      if (currentScreenUnchosen) {
        showError('Please pick a ' + (this.screen == 'decade' ? 'year' : (this.screen == 'monthyear' ? 'month' : this.screen)) + '. To skip this question and leave it blank, click \'CLEAR\' first.');
        return;
      } else {
        this.screen = this.getEmptyScreen();
      }
      this.refresh();
    }
  }
  
  this.selected = function (field, val) {
    if (field == 'decade') {
      if (this.getChoiceVal('decade') != val) {
        this.year_bucket = this.revChoiceVal('decade', val);
        this.changed = true;
        this.year = null;
      }
    } else if (field == 'year') {
      oldyear = this.year;
      this.year = val;
      if (oldyear != this.year) {
        this.changed = true;
        this.year_bucket == null;
      }
    } else if (field == 'month') {
      oldmonth = this.month;
      this.month = val;
      if (oldmonth != this.month)
        this.changed = true;
    } else if (field == 'day') {
      oldday = this.day;
      this.day = val;
      if (oldday != this.day)
        this.changed = true;
    } else if (field == 'monthyear') {
      if (this.getChoiceVal('monthyear') != val) {
        var my = this.revChoiceVal('monthyear', val);
        this.year = my.y;
        this.month = my.m;
        this.changed = true;
      }
    }
    
    var complete = false;
    var nextscreen = this.getNextScreen(this.screen);
    if (nextscreen == null) {
      if (!this.isFull()) {
        this.screen = this.getEmptyScreen();
      } else {
        //stay on current screen; must click 'next' to advance question
        complete = true;
      }
    } else {
      this.screen = nextscreen;
    }
    
    this.refresh();

    if (complete) {
      autoAdvanceTrigger();
    }
  }
  
  this.back = function () {
    if (this.isEffectivelyEmpty() || (this.isFull() && !this.changed)) {
      prevQuestion();
    } else {
      pscr = this.getPrevScreen(this.screen);
      if (pscr != null) {
        this.screen = pscr;
        this.refresh();
      } else {
        prevQuestion();
      }
    }
  }

  this.getEmptyScreen = function () {
    var screens = this.screenOrder();
    for (var i = 0; i < screens.length; i++) {
      var empty = false;
      if (screens[i] == 'decade' && this.getYearBucket() == null) {
        empty = true;
      } else if (screens[i] == 'year' && this.year == null) {
        empty = true;
      } else if (screens[i] == 'month' && this.month == null) {
        empty = true;
      } else if (screens[i] == 'day' && this.day == null) {
        empty = true;
      } else if (screens[i] == 'monthyear' && monthCount(this.year, this.month) == null) {
        empty = true;
      }
      if (empty) {
        return screens[i];
      }
    }
    return null;
  }

  this.getNextScreen = function (screen) {
    var screens = this.screenOrder();
    var i0 = (screen != null ? screens.indexOf(screen) : -1);
    for (var i = i0 + 1; i < screens.length; i++) {
      if (this.isRelevantScreen(screens[i])) {
        return screens[i];
      }
    }
    return null;
  }

  this.getPrevScreen = function (screen) {
    var screens = this.screenOrder();
    var i0 = (screen != null ? screens.indexOf(screen) : screens.length);
    for (var i = i0 - 1; i >= 0; i--) {
      if (this.isRelevantScreen(screens[i])) {
        return screens[i];
      }
    }
    return null;
  }

  this.getFirstScreen = function () {
    return this.getNextScreen(null);
  }

  this.getLastScreen = function () {
    return this.getPrevScreen(null);
  }

  this.isRelevantScreen = function (screen) {
    if (this.specificity == null) {
      return true;
    } else if (this.specificity == 'year') {
      return ['day', 'month', 'monthyear'].indexOf(screen) != -1;
    } else if (this.specificity == 'month') {
      return screen == 'day';
    }
  }

  this.getFieldOrder = function () {
    var order = [];
    var s = dateEntryOrder();
    for (var i = 0; i < 3; i++) {
      order.push(({d: 'day', m: 'month', y: 'year'})[s[i]]);
    }
    return order;
  }

  this.screensForField = function (field) {
    var candidates = [];
    if (field == 'year') {
      candidates = ['decade', 'year', 'monthyear'];
    } else if (field == 'month') {
      candidates = ['month', 'monthyear'];
    } else if (field == 'day') {
      candidates = ['day'];
    }

    var screens = []
    for (var i = 0; i < candidates.length; i++) {
      if (this.screens.indexOf(candidates[i]) != -1) {
        screens.push(candidates[i]);
      }
    }
    return screens;
  }

  this.screenOrder = function () {
    var order = [];
    var fields = this.getFieldOrder();
    for (var i = 0; i < fields.length; i++) {
      var fieldscreens = this.screensForField(fields[i]);
      for (var j = 0; j < fieldscreens.length; j++) {
        if (order.indexOf(fieldscreens[j]) == -1) {
          order.push(fieldscreens[j]);
        }
      }
    }
    return order;
  }

  this.make_decades = function () {
    if (this.screens.indexOf('decade') == -1) {
      return [{start: this.minyear, end: this.maxyear}];
    } else {
      var decades = [];
      
      var start = Math.floor((this.maxyear - this.DECADE_ROLLOVER) / 10) * 10;
      decades.push({start: start, end: this.maxyear});
      while (decades.length < this.NUM_DECADE_CHOICES) {
        start -= 10;
        decades.push({start: start, end: start + 9});
      }
      
      return decades;
    }
  }

  this.make_months = function () {
    var year = this.minyear;
    var month = this.minmonth;
    var months = [];

    while (monthCount(year, month) <= monthCount(this.maxyear, this.maxmonth)) {
      months.push({year: year, month: month});
      month += 1;
      if (month > 12) {
        year += 1;
        month = 1;
      }
    }

    return months;
  }

  this.getYearBucket = function () {
    var buckets = this.make_decades();
    if (buckets.length == 1) {
      return buckets[0];
    } else if (this.year != null) {
      for (var i = 0; i < buckets.length; i++) {
        if (buckets[i].start <= this.year && buckets[i].end >= this.year) {
          return buckets[i];
        }
      }
    } else if (this.year_bucket != null) {
      return this.year_bucket;
    } else {
      return null;
    }
  }

  this.goto_ = function (field) {
    this.screen = this.screensForField(field)[0];
    this.refresh();
  }

  this.selfunc = function (field) {
    var context = this;
    return function (ev, value, button) { context.selected(field, value, button); };
  }
}

function decadeSelect (decades, selval, context) {
  var labels = [];
  var values = [];
  var ranges = [];
  for (var i = 0; i < decades.length; i++) {
    if (decades[i].end - decades[i].start == 9 && decades[i].start % 10 == 0) {
      var label = (decades[i].start - decades[i].start % 10) + 's';
    } else if (decades[i].start % 10 == 0) {
      var label = decades[i].start + '+';
    } else {
      var label = decades[i].start + '\u2014' + decades[i].end;
    }

    labels.push(label);
    values.push(decades[i].start);
    ranges.push({start: mkNewYearsDay(decades[i].start), end: mkNewYearsEve(decades[i].end)});
  }

  var grid = render_button_grid({style: 'grid', dir: 'vert', nrows: 5, ncols: 2, width: '35@', height: '7@', spacing: '2@', textscale: 1.4, margins: '*'},
                                labels, values, false, selval, context.selfunc('decade'));
  return {layout: aspect_margin('5%-', grid.layout), get_buttons: function () { return grid.buttons; }, dateranges: ranges};
}

function yearSelect (bucket, selval, context) {
  var labels = [];
  var values = [];
  var ranges = [];
  for (var o = bucket.start; o <= bucket.end; o++) {
    labels.push(o + '');
    values.push(o);
    ranges.push({start: mkNewYearsDay(o), end: mkNewYearsEve(o)});
  }

  var grid = render_button_grid({style: 'grid', dir: 'vert',
                                 nrows: Math.min(bucket.end - bucket.start + 1, 5), ncols: Math.ceil((bucket.end - bucket.start + 1) / 5),
                                 width: (bucket.end - bucket.start) > 9 ? '22@' : '35@', height: '7@', spacing: '2@', textscale: 1.4, margins: '*'},
                                labels, values, false, selval, context.selfunc('year'));
  var layout = grid.layout;
  if (values.length <= 5) {
    //this is really, really, ugly
    var full_w = 35 * 2 + 2;
    var full_h = 7 * 5 + 2 * 4;
    var w = 35;
    var h = 7 * values.length + 2 * (values.length - 1);
    layout = new Layout({margins: '*', widths: full_w + '@', heights: full_h + '@', content: [new Layout({margins: '*', widths: (100.*w/full_w) + '%', heights: (100.*h/full_h) + '%', content: [layout]})]});
  }
  return {layout: aspect_margin('5%-', layout), get_buttons: function () { return grid.buttons; }, dateranges: ranges};
}

function monthSelect (year, selval, context) {
  var labels = [];
  var values = [];
  var ranges = [];
  for (var i = 1; i <= 12; i++) {
    labels.push(numericMonths() ? i + '' : monthName(i));
    values.push(i);
    ranges.push(year != null ? {start: mkFirstOfMonth(year, i), end: mkLastOfMonth(year, i)} : null);
  }
  var size = (numericMonths() ? 2.2 : 1.8);

  var grid = render_button_grid({style: 'grid', dir: 'horiz', nrows: 3, ncols: 4, width: '6@', height: '4@', spacing: '@', textscale: size, margins: '*'},
                                labels, values, false, selval, context.selfunc('month'));
  return {layout: aspect_margin('7%-', grid.layout), get_buttons: function () { return grid.buttons; }, dateranges: ranges};
}

function daySelect (month, year, selval, context) {
  var monthLength = daysInMonth(month, year);
  var labels = [];
  var values = [];
  var ranges = [];
  for (var i = 1; i <= monthLength; i++) {
    labels.push(i + '');
    values.push(i);
    ranges.push(monthCount(year, month) != null ? {start: mkdate(year, month, i), end: mkdate(year, month, i)} : null);
  }

  var grid = render_button_grid({style: 'grid', dir: 'horiz', nrows: 5, ncols: 7, width: '17@', height: '17@', spacing: '3@', textscale: 1.4, margins: '*'},
                                labels, values, false, selval, context.selfunc('day'));
  return {layout: aspect_margin('1.7%-', grid.layout), get_buttons: function () { return grid.buttons; }, dateranges: ranges};
}

function monthYearSelect (monthyears, selval, context) {
  var labels = [];
  var values = [];
  var ranges = [];
  for (var i = 0; i < monthyears.length; i++) {
    var item = monthyears[i];
    labels.push((numericMonths() ? intpad(item.month) + '/' : monthName(item.month) + ' ') + item.year);
    values.push(monthCount(item.year, item.month));
    ranges.push({start: mkFirstOfMonth(item.year, item.month), end: mkLastOfMonth(item.year, item.month)});
  }

  var grid = new ChoiceSelect({choices: labels, choicevals: values, action: context.selfunc('monthyear'), selected: selval});
  return {layout: grid, get_buttons: function () { return grid.buttons; }, dateranges: ranges};
}

function mkdate (y, m, d) {
  return new Date(y, m - 1, d);
}

function mkNewYearsDay (y) {
  return mkdate(y, 1, 1);
}

function mkNewYearsEve (y) {
  return mkdate(y, 12, 31);
}

function mkFirstOfMonth (y, m) {
  return mkdate(y, m, 1);
}

function mkLastOfMonth (y, m) {
  return mkdate(y, m, daysInMonth(m, y));
}

function intpad (x, n) {
  var s = x + '';
  while (s.length < n) {
    s = '0' + s;
  }
  return s;
}

function monthName (mnum) {
  if (mnum == null)
    return null;

  if (mnum >= 1 && mnum <= 12) {
    return monthNames[mnum - 1];
  } else {
    throw new Error(mnum + ' not a valid month');
  }
}
       
function monthForName (mname) {
  if (mname == null)
    return null;

  var mnum = monthNames.indexOf(mname);
  if (mnum != -1) {
    return mnum + 1;
  } else {
    throw new Error(mname + ' not a valid month');
  }
}

function isLeap (year) {
  return (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0));
}

function daysInMonth (month, year) {
  if (month == null)
    return 31;
  if (year == null && month == 2)
    return 28;

  if (month == 2) {
    return 28 + (isLeap(year) ? 1 : 0);
  } else if (month == 4 || month == 6 || month == 9 || month == 11) {
    return 30;
  } else {
    return 31;
  }
}

function monthCount (year, month) {
  return (year == null || month == null ? null : 12 * year + month - 1);
}

function rangeOverlap (start0, end0, start1, end1) {
  end1 = end1 || start1;
  return Math.max(start0, start1) <= Math.min(end0, end1);
}

function parseDate (datestr) {
  var year = +datestr.substring(0, 4);
  var month = +datestr.substring(5, 7);
  var day = +datestr.substring(8, 10);
  return {year: year, month: month, day: day};
}

function readableDate (y, m, d) {
  return (y >= 1900 && y <= 2050 ? monthName(m) + ' ' + d + ', ' + y : 'anything');
}

