
function getForm(o) {
  var form = o.parent;
  while (form.parent) {
    form = form.parent;
  }
  return form;
}

//if index is part of a repeat, return only the part beyond the deepest repeat
function relativeIndex(ix) {
  var steps = ix.split(',');
  var deepest_repeat = -1;
  for (var i = steps.length - 2; i >= 0; i--) {
    if (steps[i].indexOf(':') != -1) {
      deepest_repeat = i;
      break;
    }
  }
  if (deepest_repeat == -1) {
    return ix;
  } else {
    var rel_ix = '-';
    for (var i = deepest_repeat + 1; i < steps.length; i++) {
      rel_ix += steps[i] + (i < steps.length - 1 ? ',' : '');
    }
    return rel_ix;
  }
}

function getIx(o) {
  var ix = o.rel_ix;
  while (ix[0] == '-') {
    o = o.parent;
    if (!o) {
      break;
    }
    if (o.rel_ix.split(',').slice(-1)[0].indexOf(':') != -1) {
      ix = o.rel_ix + ',' + ix.substring(1);
    }
  }
  return ix;
}

function getForIx(o, ix) {
  if (o.type == 'question') {
    return (getIx(o) == ix ? o : null);
  } else {
    for (var i = 0; i < o.children.length; i++) {
      var result = getForIx(o.children[i], ix);
      if (result) {
        return result;
      }
    }
  }
}

function ixInfo(o) {
  var full_ix = getIx(o);
  return o.rel_ix + (o.is_repetition ? '(' + o.uuid + ')' : '') + (o.rel_ix != full_ix ? ' :: ' + full_ix : '');
}

function empty_check(o, anim_speed) {
  if (o.type == 'repeat-juncture' || o.type == 'sub-group') {
    var empty = (o.children.length == 0);
    if (anim_speed) {
      o.$empty[empty ? 'slideDown' : 'slideUp'](anim_speed);
    } else {
      o.$empty[empty ? 'show' : 'hide']();
    }
  }
}

function loadFromJSON(o, json) {
  $.each(json, function(key, val) {
      if (key == 'children') {
        return;
      } else if (key == 'ix') {
        key = 'rel_ix';
        val = relativeIndex(val);
      } else if (key == 'answer') {
        key = 'last_answer';
      } else if (key == 'style') {
        key = 'domain_meta';
        val = parse_meta(json.datatype, val);
      }

      o[key] = val;
    });
}

function parse_meta(type, style) {
  var meta = {};
  
  if (type == "date") {
    meta.mindiff = style.before != null ? +style.before : null;
    meta.maxdiff = style.after != null ? +style.after : null;
  } else if (type == "int" || type == "float") {
    meta.unit = style.unit;
  } else if (type == 'str') {
    meta.autocomplete = (style.mode == 'autocomplete');
    meta.autocomplete_key = style["autocomplete-key"];
    meta.mask = style.mask;
    meta.prefix = style.prefix;
    meta.longtext = (style.raw == 'full');
  } else if (type == "multiselect") {
    if (style["as-select1"] != null) {
      meta.as_single = [];
      var vs = style["as-select1"].split(',');
      for (var i = 0; i < vs.length; i++) {
        var k = +vs[i];
        if (k != 0) {
          meta.as_single.push(k);
        }
      }
    }
  }
  
  return meta;
}

function Form(json, adapter) {
  this.adapter = adapter;
  this.children = [];

  this.init_render = function() {
    this.$container = $('<div><h1 id="title"></h1><div id="form"></div><input id="submit" type="submit" value="Submit" /></div>');
    this.$title = this.$container.find('#title');
    this.$children = this.$container.find('#form');

    this.$title.text(json.title);
    render_elements(this, json.tree);

    var form = this;
    this.$container.find('#submit').click(function() {
        var proceed = adapter.presubmitfunc();
        if (!proceed) {
          return;
        }

        form.submit();
      });

    this.submit = function() {
      this.adapter.submitForm(this);
    }
  }

  this.reconcile = function(new_json) {
    reconcile_elements(this, new_json);
  }

  this.child_container = function() {
    return this.$children;
  }

  this.submitting = function() {
    $('#submit').val('Submitting...');
  }
}

function Group(json, parent) {
  loadFromJSON(this, json);
  this.parent = parent;
  this.is_repetition = parent.is_repeat;
  this.children = [];

  this.init_render = function() {
    this.$container = $('<div class="gr"><div class="gr-header"><span id="caption"></span> <span id="ix"></span> <a id="del" href="#">delete</a></div><div id="children"></div><div id="empty">This group is empty</div></div>');
    this.$children = this.$container.find('#children');
    this.$caption = this.$container.find('#caption');
    this.$ix = this.$container.find('#ix');
    this.$empty = this.$container.find('#empty');

    render_elements(this, json.children);
    this.update();

    this.$del = this.$container.find('#del');
    if (!this.is_repetition) { //todo: check constraints
      this.$del.hide();
    }

    var g = this;
    this.$del.click(function() {
        g.deleteRepeat();
        return false;
      });
  }

  this.deleteRepeat = function() {
    getForm(this).adapter.deleteRepeat(this);
  }

  this.reconcile = function(new_json) {
    this.caption = new_json.caption;
    if (this.is_repetition) {
      this.rel_ix = relativeIndex(new_json.ix);
    }
    reconcile_elements(this, new_json.children);    
    this.update();
  }

  this.update = function() {
    this.$caption.text(this.caption);
    this.$ix.text('[' + ixInfo(this) + ']');
  }

  this.destroy = function() {

  }

  this.child_container = function() {
    return this.$children;
  }
}

function Repeat(json, parent) {
  loadFromJSON(this, json);
  this.parent = parent;
  this.children = [];
  this.is_repeat = true;

  this.init_render = function() {
    this.$container = $('<div class="rep"><div class="rep-header"><span id="caption"></span> <span id="ix"></span> <a id="add" href="#">add new</a></div><div id="children"></div><div id="empty">This repeatable group is empty</div></div>');
    this.$children = this.$container.find('#children');
    this.$header = this.$container.find('#caption');
    this.$ix = this.$container.find('#ix');
    this.$empty = this.$container.find('#empty');

    render_elements(this, json.children);
    this.update();

    this.$add = this.$container.find('#add');
    var rep = this;
    this.$add.click(function() {
        rep.newRepeat();
        return false;
      });
  }

  this.newRepeat = function() {
    getForm(this).adapter.newRepeat(this);
  }

  this.reconcile = function(new_json) {
    this['main-header'] = new_json['main-header'];
    reconcile_elements(this, new_json.children);
    this.update();
  }

  this.update = function() {
    this.$header.text(this['main-header']);
    this.$ix.text('[' + ixInfo(this) + ']');
  }

  this.destroy = function() {

  }

  this.child_container = function() {
    return this.$children;
  }
}

function Question(json, parent) {
  loadFromJSON(this, json);
  this.parent = parent;
  this.children = [];

  this.is_select = (this.datatype == 'select' || this.datatype == 'multiselect');

  this.init_render = function() {
    if (this.datatype != 'info') {
      this.$container = $('<div class="q"><div id="widget"></div><span id="req"></span><span id="caption"></span> <span id="ix"></span> <div id="error"></div><div class="eoq" /></div>');
      this.$error = this.$container.find('#error');

      this.update(true);
    } else {
      this.$container = $('<div><span id="ix"></span><span id="caption"></span></div>');
      this.$container.addClass('info');
      this.control = new InfoEntry();

      this.update(false);
    }
  }

  this.reconcile = function(new_json) {
    this.caption = new_json.caption;
    this.required = new_json.required;

    var refresh_widget = false;
    if (this.is_select) {
      var different = false;
      if (this.choices.length != new_json.choices.length) {
        different = true;
      } else {
        $.each(this.choices, function(i, e) {
            if (e != new_json.choices[i]) {
              different = true;
              return false;
            }
          });
      }

      if (different) {
        this.choices = new_json.choices;
        this.last_answer = new_json.answer;
        refresh_widget = true;
      }
    }

    this.update(refresh_widget);
  }

  // this is kind of hacked up how we update select questions. generally input widgets
  // themselves aren't altered as the rest of the form changes, but select choices can
  // change due to locale switches or itemsets. ideally we should create the widget once
  // and call a reconcile() function on it, but: the select widget is currently pretty
  // complicated due to vestigial code, and the ajax api doesn't provide the select
  // values, so we can't accurately map which old choices correspond to which new
  // choices. so instead we destroy and recreate the control here, and it's messy.
  // it also screws up the focus, which we'd have to take extra steps to preserve, but
  // don't currently.

  this.update = function(refresh_widget) {
    this.$container.find('#caption').text(this.caption);
    this.$container.find('#req').text(this.required ? '*' : '');
    this.$container.find('#ix').text('[' + ixInfo(this) + ']');

    if (refresh_widget) {
      //var uistate = this.control.get_ui_state();

      this.$container.find('#widget').empty();
      this.control = renderQuestion(this, this.$container.find('#widget'), this.last_answer);

      //this.control.restore_ui_state(uistate);
    }
  }

  this.getAnswer = function() {
    return this.control.getAnswer();
  }

  this.prevalidate = function() {
    return this.control.prevalidate(this);
  }

  this.onchange = function() {
    if (this.prevalidate()) {
      //check if answer has actually changed
      if (['select', 'multiselect', 'date'].indexOf(this.datatype) != -1) {
        //free-entry datatypes are suitably handled by the 'onchange' event
        var new_answer = this.getAnswer();
        if (answer_eq(this.last_answer, new_answer)) {
          return;
        }
      }

      this.last_answer = this.getAnswer();
      this.commitAnswer();
    }
  }

  this.commitAnswer = function() {
    getForm(this).adapter.answerQuestion(this);
  }

  this.showError = function(content) {
    this.$error.text(content ? content : '');
    this.$container[content ? 'addClass' : 'removeClass']('qerr');
  }

  this.clearError = function() {
    this.showError(null);
  }


  this.destroy = function() {
    this.control.destroy();
  }
}

function make_element(e, parent) {
  if (e.type == 'question') {
    var o = new Question(e, parent);
  } else if (e.type == 'sub-group') {
    var o = new Group(e, parent);
  } else if (e.type == 'repeat-juncture') {
    var o = new Repeat(e, parent);
  }
  o.init_render();
  return o;
}

function render_elements(parent, elems) {
  for (var i = 0; i < elems.length; i++) {
    var o = make_element(elems[i], parent);
    parent.children.push(o);
    parent.child_container().append(o.$container);
  }
  empty_check(parent);
}

function reconcile_elements(parent, new_elems) {
  var mapping = [];
  for (var i = 0; i < parent.children.length; i++) {
    var child = parent.children[i];
    mapping.push([child, inElementSet(child, new_elems)]);
  }
  for (var i = 0; i < new_elems.length; i++) {
    var new_elem = new_elems[i];
    if (inElementSet(new_elem, parent.children) == null) {
      mapping.push([null, new_elem]);
    }
  }

  $.each(mapping, function(i, val) {
      var e_old = val[0];
      var e_new = val[1];

      if (e_old == null) {
        var o = make_element(e_new, parent);
        addChild(parent, o, new_elems);
      } else if (e_new == null) {
        deleteChild(parent, e_old);
      } else {
        e_old.reconcile(e_new);
      }
    });
}

function deleteChild(parent, child) {
  child.$container.slideUp('slow', function() {
      child.$container.remove();
      child.destroy();
      arrayDelItem(parent.children, child);
      empty_check(parent, 'fast');
    });
}

function addChild(parent, child, final_ordering) {
  var newIx = ixElementSet(child, final_ordering);
  var insertionIx = 0;
  for (var k = newIx - 1; k >= 0; k--) {
    var precedingIx = ixElementSet(final_ordering[k], parent.children);
    if (precedingIx != -1) {
      insertionIx = precedingIx + 1;
      break;
    }
  }

  var domInsert = function(insert) {
    child.$container.hide();
    insert(child.$container);
    child.$container.slideDown();
  }

  if (insertionIx < parent.children.length) {
    domInsert(function(e) { parent.children[insertionIx].$container.before(e); });
  } else {
    domInsert(function(e) { parent.child_container().append(e); });
  }
  arrayInsertAt(parent.children, insertionIx, child);
  empty_check(parent, 'slow');
}

function arrayDel(arr, i) {
  return arr.splice(i, 1)[0];
}

function arrayDelItem(arr, o) {
  var ix = arr.indexOf(o);
  if (ix != -1) {
    arrayDel(arr, ix);
  }
}

function arrayInsertAt(arr, i, o) {
  arr.splice(i, 0, o);
}

var cmpkey = function (e) {
  if (e.uuid) {
    return 'uuid-' + e.uuid;
  } else {
    return 'ix-' + (e.ix ? e.ix : getIx(e));
  }
}

var ixElementSet = function(e, set) {
  //return the index of the matching element of 'e' within 'set'; -1 if no match
  return $.map(set, function(val) { return cmpkey(val); }).indexOf(cmpkey(e));
}

var inElementSet = function(e, set) {
  //return the matching object of 'e' within 'set'; null if no match
  ix = ixElementSet(e, set);
  return (ix != -1 ? set[ix] : null);
}

function init_render(form, adapter, $div) {
  var f = new Form(form, adapter);
  f.init_render();
  $div.append(f.$container);
  return f;
}

var answer_eq = function(ans1, ans2) {
  if (ans1 === ans2) {
    return true;
  } else if (ans1 instanceof Array && ans2 instanceof Array) {
    if (ans1.length == ans2.length) {
      for (var i = 0; i < ans1.length; i++) {
        if (ans1[i] != ans2[i]) {
          return false;
        }
      }
      return true;
    }
  }
  return false;
}

function scroll_pin(pin_threshold, $container, $elem) {
  var base_offset = $container.offset().top;
  var pos_type = $elem.css('position');

  return function() {
    var scroll_pos = $(window).scrollTop();
    var elem_pos = base_offset - scroll_pos;
    var pinned = (elem_pos < pin_threshold);

    $elem.css('position', pinned ? 'fixed' : pos_type);
    $elem.css('top', pinned ? pin_threshold + 'px' : 0);
  };
}
  
function set_pin(pin_threshold, $container, $elem) {
  var pinfunc = scroll_pin(pin_threshold, $container, $elem);
  $(window).scroll(pinfunc);
  pinfunc();
}

