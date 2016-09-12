
function removeAllChildren (element) {
  while (element.hasChildNodes()) {
    element.removeChild(element.firstChild);
  }
}

function render_viewport (vp, scene_graph) {
  var viewport = document.getElementById(vp);
  removeAllChildren(viewport);
  scene_graph.render(viewport);
}

function Indirect (key) {
  this.key;
  this.parent = null;
  this.content = null;
  
  this.setParent = function (parent) {
    this.parent = parent;
  }
  
  this.update = function (content) {
    this.content = content;
    this.parent.update(this);
  }
}

/*
 * make a grid layout, where each grid cell can have pluggable child content
 * args == {id, nrows, ncols, widths, heights, margins, spacings, color, margin_color, spacing_color, content}
 * id: id of the containing div
 * nrows: number of grid rows, default: 1
 * ncols: number of grid columns, default: 1
 * widths: widths of columns; either an array of individual widths, or a scalar width for all columns; default: '*'
 * heights: heights of rows; either an array of individual heights, or a scalar height for all rows; default: '*'
 * margins: margins around the edge of the grid; either a 4-element array (left, right, top, bottom), 2-elem (left/right, top/bottom), or scalar (same for all); default: 0
 * spacings: intra-cell spacings; 2-elem array (horizontal, vertical), or scalar to use the same for both; default: 0
 * color: grid cell color, uses parent's color if null
 * margin_color: margin color, uses parent's color if null, '-' to re-use 'color'
 * spacing_color: inter-cell space color, uses parent's color if null, '-' to re-use 'color'
 * content: array of child elements for each grid cell, left-to-right, then top-to-bottom
 * 
 * dimension spec for width/height/margin/spacing; dimensions can be specified as:
 *   - raw pixels (e.g., 86)
 *   - percentage of available space (e.g., '10%')
 *     percentages can have an optional modifier afterward:
 *     - 10%- -- 10% of the smaller of the horizontal or vertical dimension
 *     - 10%+ -- 10% of the larger of the horizontal or vertical dimension
 *     - 10%= -- 10% of the geometric mean of the two dimensions
       note that +, -, and = will give an aspect-ratio-locked result
 *     - appending ! will calculate relative to the total screen size dimensions, ignoring the dimensions of the current pane
 *   - proportional share of aspect-ratio-locked remaining space (e.g., '0.6@') -- similar to '*', but a unit of '@' is guaranteed to be equal in both the horizontal and vertical dimension
 *   - proportional share of remaining space (e.g., '2.5*') after all other space is allocated
 *   directives take precedence in the order listed
 *   if you're not careful, it's possible to choose sizes that exceed the available space; layout and behavior may become unpredictable
 */
function Layout (args) {
  this.id = args.id;

  this.nrows = args.nrows || 1;
  this.ncols = args.ncols || 1;
  if (this.nrows < 1 || this.ncols < 1) {
    throw new Error("invalid dimensions");
  }
  
  var widths = args.widths || '*';
  if (widths instanceof Array) {
    if (widths.length != this.ncols) {
      throw new Error("widths don't match # cols");
    }
    this.widths = widths;
  } else { //single width to use for all columns
    this.widths = [];
    for (i = 0; i < this.ncols; i++) {
      this.widths.push(widths)
    }
  }

  var heights = args.heights || '*';
  if (heights instanceof Array) {
    if (heights.length != this.nrows) {
      throw new Error("heights don't match # rows");
    }
    this.heights = heights;
  } else { //single height to use for all rows
    this.heights = [];
    for (i = 0; i < this.nrows; i++) {
      this.heights.push(heights)
    }
  }

  var margins = args.margins || 0;
  if (margins instanceof Array) {
    if (margins.length != 2 && margins.length != 4) {
      throw new Error("invalid margins");
    }
    if (margins.length == 2) {
      this.l_margin = margins[0];
      this.r_margin = margins[0];
      this.t_margin = margins[1];
      this.b_margin = margins[1];  
    } else {
      this.l_margin = margins[0];
      this.r_margin = margins[1];
      this.t_margin = margins[2];
      this.b_margin = margins[3];  
    }
  } else {
    this.l_margin = margins;
    this.r_margin = margins;
    this.t_margin = margins;
    this.b_margin = margins;
  }
  
  var spacings = args.spacings || 0;
  if (spacings instanceof Array) {
    if (spacings.length != 2) {
      throw new Error("invalid margins");
    }
    this.h_spacing = spacings[0];
    this.v_spacing = spacings[1];
  } else {
    this.h_spacing = spacings;
    this.v_spacing = spacings;
  }
  
  this.content = args.content;
  if (this.content.length != this.nrows * this.ncols) {
    throw new Error('not enough child content for layout! expected: ' + (this.nrows * this.ncols) + ' got: ' + this.content.length);
  }
  for (var i = 0; i < this.content.length; i++) {
    if (this.content[i] instanceof Indirect) {
      this.content[i].setParent(this);
    }
  }
  
  this.color = args.color;
  this.margin_color = (args.margin_color == '-' ? args.color : args.margin_color);
  this.spacing_color = (args.spacing_color == '-' ? args.color : args.spacing_color);

  this.container = null;
  this.child_index = []; //[list of div for each child]
  
  this.update = function (ind) {
    var position = this.content.indexOf(ind);
    
    if (this.container == null)
      return; //do nothing else if layout object has not been rendered yet
    
    var subcontent = ind.content;
    if (subcontent != null && subcontent.container != null) {
      var domNew = subcontent.container;
      this.container.replaceChild(domNew, this.child_index[position]);
    } else {
      var domOld = this.child_index[position];
      var r = Math.floor(position / this.ncols);
      var c = position % this.ncols;
      var x = domOld.offsetLeft;
      var y = domOld.offsetTop;
      var w = domOld.clientWidth;
      var h = domOld.clientHeight;
      var domNew = new_div(subcontent != null ? subcontent.id : this.container.id + '-' + null + '-' + r + '-' + c, y, x, w, h);
      set_color(domNew, this.color, this.container.style.backgroundColor);

      this.container.replaceChild(domNew, this.child_index[position]);
      if (subcontent != null) {
        subcontent.render(domNew);
      }
    }
    this.child_index[position] = domNew;
  }
  
  this.render = function (parent) {
    render_layout(this, parent);
  }
}

function render_layout (layout, parent_div) {
  var dimensions = partition({
      id: layout.id,
      screen_width: SCREEN_WIDTH,
      screen_height: SCREEN_HEIGHT,
      pane_width: parent_div.clientWidth,
      pane_height: parent_div.clientHeight,
      widths: layout.widths,
      heights: layout.heights,
      lmargin: layout.l_margin,
      rmargin: layout.r_margin,
      tmargin: layout.t_margin,
      bmargin: layout.b_margin,
      hspacing: layout.h_spacing,
      vspacing: layout.v_spacing
    });
  var widths = dimensions[0];
  var heights = dimensions[1];
  var woff = offsets(widths);
  var hoff = offsets(heights);
  var parent_color = parent_div.style.backgroundColor;
  
  if (has_margins(widths, heights)) {
    var inner_area = new_div(parent_div.id + '-inner', hoff[1], woff[1], ainv(woff, -1) - widths[0], ainv(hoff, -1) - heights[0]);
    parent_div.appendChild(inner_area);
    set_color(parent_div, layout.margin_color, parent_color);
  } else {
    var inner_area = parent_div;
  }
  
  if (has_spacing(widths, heights)) {
    set_color(inner_area, layout.spacing_color, parent_color);
  }
  
  layout.child_index = [];
  for (var r = 0; r < layout.nrows; r++) {
    for (var c = 0; c < layout.ncols; c++) {
      var x = woff[2*c + 1];
      var y = hoff[2*r + 1];
      var w = widths[2*c + 1];
      var h = heights[2*r + 1];
      
      var subcontent = layout.content[layout.ncols * r + c];
      if (subcontent instanceof Indirect) {
        subcontent = subcontent.content;
      }
      
      if (subcontent == null || subcontent.container == null) {
        var subcell = new_div(subcontent != null ? subcontent.id : parent_div.id + '-' + null + '-' + r + '-' + c, y, x, w, h);
        layout.child_index.push(subcell);
      
        set_color(subcell, layout.color, parent_color);
        parent_div.appendChild(subcell);
        if (subcontent != null) {
          subcontent.render(subcell);
        }
      } else {
        layout.child_index.push(subcontent.container);
        parent_div.appendChild(subcontent.container);
      }
    }
  }
  
  layout.container = parent_div;
}

function has_margins (widths, heights) {
  return widths[0] > 0 || ainv(widths, -1) > 0 || heights[0] > 0 || ainv(heights, -1) > 0;
}

function has_spacing (widths, heights) {
  return (widths.length > 3 || heights.length > 3) && (widths[2] > 0 || heights[2] > 0);
}

function ChoiceButton (args) {
  this.label = args.label;
  this.value = (args.value != null ? args.value : this.label);
  this.multi = args.multi || false;
  this.default_color = args.color;
  this.selected_color = args.selcolor;
  this.inactive_color = args.inactcolor;
  this.base_style = args.style;
  this.centered = args.centered;

  this.flashcounter = 0;

  this.init = function (args) {
    this.make_button = function (args) {
      var button = this;
      var onclick = function (ev) {
        if (args.action != null && button.status != 'disabled') {
          args.action(ev, button.value, button);
        }
      };

      return new TextButton({
          id: 'button-' + this.value,
          caption: '',
          color: null,
          style: null,
          textcolor: args.textcolor,
          textsize: args.textsize,
          onclick: onclick,
          centered: this.centered && !this.multi
        });
    }
    this.button = this.make_button(args);
    this.setStatus('default');
  }

  this.setStatus = function (stat) {
    this.status = stat;

    this.button.setText((this.multi ? (this.status == 'selected' ? '\u2612' : '\u2610') + ' ' : '') + this.label);
    var styleSet = this.setClass();
    if (!styleSet) {
      this.setColor();
    }
  }

  this.setColor = function () {
    if (this.status == 'default') {
      this.button.setColor(this.default_color);
    } else if (this.status == 'selected') {
      if (this.selected_color == null)
        console.log('no selected color set!');
      this.button.setColor(this.selected_color);
    } else if (this.status == 'disabled') {
      if (this.inactive_color == null)
        console.log('no disabled color set!');
      this.button.setColor(this.inactive_color);
    }
  }

  this.setClass = function() {
    if (supportsGradient()) {
      if (this.status == 'default') {
        return this.button.setStyle(this.base_style);
      } else if (this.status == 'selected') {
        return this.button.setStyle(this.base_style != null ? 'selected ' + this.base_style : null);
      } else if (this.status == 'disabled') {
        //'disabled' style doesn't exist; commenting out until it does as it prevent the disabled color from taking effect
        //not sure disabled buttons need the 3-d effect anyway
        //this.button.setStyle(this.base_style != null ? this.base_style + ' disabled' : null);
        return this.button.setStyle(null);
      }
    }
    return false;
  }    

  this.toggleStatus = function () {
    if (this.status != 'disabled') {
      this.setStatus(this.status == 'default' ? 'selected' : 'default');
    }
  }

  this.resetStatus = function () {
    if (this.status != 'disabled') {
      this.setStatus('default');
    }
  }

  this.flash = function(len) {
    if (len > 0) {
      this.setStatus('selected');
      this.flashcounter++;
      var button = this;
      setTimeout(function () {
          button.flashcounter--;
          if (button.flashcounter == 0) {
            button.setStatus('default');
          }
        }, len);
    }
  }

  this.render = function (parent_div) {
    this.button.render(parent_div);
  }

  this.init(args);
}

//todo: auto-sizing?
function TextButton (args) {
  this.id = args.id;
  this.caption = args.caption;
  this.color = args.color;
  this.text_color = args.textcolor;
  this.size_rel = args.textsize;
  this.onclick = args.onclick;
  this.centered = (args.centered != null ? args.centered : true);
  this.style = args.style;

  this.container = null;
  this.span = null;
  this.render = function (parent_div) {  
    this.container = parent_div;
    parent_div.id = uid(this.id);
    this.setColor(this.color);
    this.setStyle(this.style);
    parent_div.innerHTML = '<table border="0" cellpadding="0" cellspacing="0" width="100%" height="100%"><tr><td align="' + (this.centered ? 'center' : 'left') + '" valign="middle"><span></span></td></tr></table>'
    span = parent_div.getElementsByTagName('span')[0];
    span.style.fontWeight = 'bold';
    span.style.fontSize = this.size_rel * 100. + '%';
    span.style.color = this.text_color;
    span.textContent = this.caption;
    setClickEvent(parent_div, this.onclick);
    if (!this.centered) {
      span.style.marginLeft = .25 * parent_div.clientHeight + 'px';
    }
    this.span = span;
    parent_div.style.MozBorderRadius = '10px';
    parent_div.style.BorderRadius = '10px';
    parent_div.style.WebkitBorderRadius = '10px';
  }

  this.setText = function (text) {
    this.caption = text;
    if (this.span != null)
      this.span.textContent = text;
  }

  this.setColor = function (color) {
    this.color = color;
    if (this.container != null) {
      set_color(this.container, this.color);
    }
  }

  this.setStyle = function (style) {
    this.style = style;
    if (this.container != null) {
      this.container.setAttribute("class", this.style);
    }
    return (style != null);
  }
}

function TextCaption (args) {
  this.id = args.id;
  this.color = args.color || '#444';
  this.caption = args.caption || '';
  this.size_rel = args.size || 1.;
  this.align = args.align || 'center';
  this.valign = args.valign || 'middle';
  this.fit = (args.fit == null ? true : args.fit);
  this.minsize = args.minsize || this.size_rel / 2.;

  this.container = null;
  this.span = null;
  this.render = function (parent_div) {
    this.container = parent_div;
    parent_div.id = uid(this.id);
    parent_div.innerHTML = '<table border="0" cellpadding="0" cellspacing="0" width="100%" height="100%"><tr><td align="' + this.align + '" valign="' + this.valign + '"><span></span></td></tr></table>'
    span = parent_div.getElementsByTagName('span')[0];
    span.style.fontWeight = 'bold';
    span.style.fontSize = this.size_rel * 100. + '%';
    span.style.color = this.color;
    span.textContent = this.caption;
    this.span = span;
  }
  
  this.setText = function (text) {
    this.caption = text;
    if (this.span != null) {
      this.span.textContent = text;
      if (this.fit) {
        this.span.style.fontSize = (100. * fitText(text, this.container, this.minsize, this.size_rel)) + '%';
      }
    }
  }

}

fitText = function(text, container, min_size, max_size) {
  var BUFFER = 0.02;
  var w = container.clientWidth * (1. - BUFFER);
  var h = container.clientHeight;
  var EPSILON = BUFFER * min_size / 2.;

  var curSize = max_size;
  var ext = getTextExtent(text, curSize, w);
  if (ext[0] > w || ext[1] > h) {
    var minSize = min_size;
    var maxSize = max_size;

    while (Math.abs(maxSize - minSize) > EPSILON) {
      curSize = (minSize + maxSize) / 2;
      ext = getTextExtent(text, curSize, w);
      if (ext[0] > w || ext[1] > h) {
        maxSize = curSize;
      } else {
        minSize = curSize;
      }		
    }

    //pixels don't perfectly scale with text size, so we do this final 'nudging' to
    //correct for any irregularities
    while (ext[0] > w || ext[1] > h) {
      curSize -= EPSILON;
      ext = getTextExtent(text, curSize, w);
    }
  }
  
  return curSize;
}

function TextInput (args) {
  this.id = args.id;
  this.color = args.color || '#000';
  this.bgcolor = args.bgcolor;
  this.content = args.content || '';
  this.size_rel = args.textsize || 1.;
  this.align = args.align || 'center';
  this.spacing = args.spacing;
  this.passwd = args.passwd || false;
  this.maxlen = args.maxlen || -1;

  this.container = null;
  this.control = null;
  this.render = function (parent_div) {
    this.container = parent_div;
    parent_div.innerHTML = '<table border="0" cellpadding="0" cellspacing="0" width="100%" height="100%"><tr><td valign="middle"><input></input></td></tr></table>'
    inp = parent_div.getElementsByTagName('input')[0];
    inp.id = uid(this.id);

    set_color(parent_div, this.bgcolor, parent_div.style.backgroundColor);
    inp.style.backgroundColor = (this.bgcolor != null ? this.bgcolor : parent_div.style.backgroundColor);
    inp.style.color = this.color;
    inp.style.borderWidth = '0px';
    inp.style.height = '100%';
    inp.style.width = '100%';
    inp.style.fontWeight = 'bold';
    inp.style.fontSize = this.size_rel * 100. + '%';
    inp.style.textAlign = this.align;
    if (this.spacing != null) {
      inp.style.letterSpacing = this.spacing + 'px';
    }
    inp.value = this.content;
    inp.type = (this.passwd ? 'password' : 'text');
    this.control = inp;
    this.setMaxLen(this.maxlen);
  }
  
  this.setText = function (text) {
    this.content = text;
    if (this.control != null)
      this.control.value = text;
  }

  this.setMaxLen = function (maxlen) {
    maxlen = maxlen || -1;
    this.maxlen = maxlen;
    if (this.control != null)
      this.control.maxLength = maxlen;
  }
}

function norm_selected (sel) {
  if (sel == null) {
    return null;
  } else {
    return (sel instanceof Array ? sel : [sel]);
  }
}

function unzip_choices (labels, values) {
  if (labels[0] instanceof Object && values == null) {
    var labs = [];
    var vals = [];
    for (var i = 0; i < labels.length; i++) {
      labs.push(labels[i].lab);
      vals.push(labels[i].val);      
    }
    return {labels: labs, values: vals}
  } else {
    return {labels: labels, values: values}
  }
}

function ChoiceSelect (args) {
  var cv = unzip_choices(args.choices, args.choicevals);
  this.choices = cv.labels;
  this.values = cv.values;
  this.multi = args.multi || false;
  this.onclick = args.action;
  this.selected = norm_selected(args.selected); //todo: improve this
  this.layout_override = args.layout_override || {};
  this.style = args.style;

  this.buttons = null;

  this.render = function (parent_div) {
    var layout_params = layout_choices(parent_div, this.choices, this.multi, this.layout_override);
    var render_data = render_button_grid(layout_params, this.choices, this.values, this.multi, this.selected, this.onclick, this.style);
    var layout = render_data.layout;
    this.buttons = render_data.buttons;
    layout.render(parent_div);
  }
}

//given a set of choice captions, determine optimum layout of choice buttons to maximize aesthetics
function layout_choices (parent_div, choices, multi, override) {
  //layout constants
  var MAX_TEXT_SIZE_GRID = override.maxText || 2.5;
  var MAX_TEXT_SIZE_LIST = override.maxText || 1.8;
  var MIN_TEXT_SIZE = .3;
  var MAX_LENGTH_FOR_GRID = 350.;  //px: need to dynamicize
  var MAX_LENGTH_DIFF_FOR_GRID_ABS = 125; //px: need to dynamicize
  var MAX_LENGTH_DIFF_FOR_GRID_REL = 2.2;
  var DIFF_REF_THRESHOLD = 50.; //px: need to dynamicize
  var BUFFER_MARGIN = override.margin || 32; //px: need to dynamicize

  if (override.spacing) {
    var SPACING_RATIO = override.spacing;
  } else if (choices.length <= 6) {
    var SPACING_RATIO = .15;
  } else if (choices.length <= 12) {
    var SPACING_RATIO = .1;
  } else {
    var SPACING_RATIO = .05;
  }

  //available size of choice area
  var W_MAX = parent_div.clientWidth - BUFFER_MARGIN;
  var H_MAX = parent_div.clientHeight - BUFFER_MARGIN;
  var GOLDEN_RATIO = W_MAX / H_MAX;

  //determine whether to use grid-based layout (centered, buttons oriented in grid pattern)
  //or list-based layout (left-justified, vertical orientation)
  var lengths = [];
  var min_w = -1;
  var max_w = -1;
  var h = -1;
  var longest_choice = null;
  for (i = 0; i < choices.length; i++) {
    var ext = getChoiceExtent(choices[i], 1.);
    var w = ext[0];
    h = ext[1];
    lengths.push(w);
    if (min_w == -1 || w < min_w)
      min_w = w;
    if (max_w == -1 || w > max_w) {
      max_w = w;
      longest_choice = choices[i];
    }
  }
  if (override.forceMode != null) {
    style = override.forceMode;
  } else if (max_w > MAX_LENGTH_FOR_GRID || max_w - min_w > MAX_LENGTH_DIFF_FOR_GRID_ABS || (min_w >= DIFF_REF_THRESHOLD && max_w/min_w > MAX_LENGTH_DIFF_FOR_GRID_REL)) {
    style = 'list';
  } else {
    style = 'grid';
  }

  //todo: use binary search for text sizing?

  if (style == 'grid') {
    var margins = '*';

    //determine best grid dimensions -- layout that best approaches GOLDEN_RATIO
    buttondim = buttonDimensions([max_w, h]);
    best_arrangement = null;
    zvalue = -1;
    for (var r = 1; r <= choices.length; r++) {
      c = Math.ceil(choices.length / r);
      spc = buttondim[1] * .33;
      spc = (spc > 40 ? 40 : (spc < 15 ? 15 : spc));
      ratio = (buttondim[0] * c + spc * (c - 1)) / (buttondim[1] * r + spc * (r - 1));
      z = (ratio < GOLDEN_RATIO ? GOLDEN_RATIO / ratio : ratio / GOLDEN_RATIO);
      if (r * c == choices.length) { //bonus for grid being completely filled
        z -= .75
          }
      if (zvalue == -1 || z < zvalue) {
        zvalue = z;
        best_arrangement = [r, c];
      }
    }
    rows = best_arrangement[0];
    cols = best_arrangement[1];    
    var dir = (rows > cols ? 'vert' : 'horiz'); //determine orientation

    //determine best button sizing -- largest sizing that will fit within allowed area
    for (size = MAX_TEXT_SIZE_GRID; size >= MIN_TEXT_SIZE; size -= .1) {
      var ext = buttonDimensions(getChoiceExtent(longest_choice, size, multi));
      bw = ext[0];
      bh = ext[1];
      best_spc = -1;
      zvalue = -1;
      //determine best inter-button spacing for given size -- where ratio of button area to inter-button area best approaches SPACING_RATIO
      for (spc = 5; spc <= 50; spc += 5) {
        w_total = (cols * bw + (cols - 1) * spc);
        h_total = (rows * bh + (rows - 1) * spc);
        k0 = bw * bh * rows * cols;
        k1 = w_total * h_total;
        ratio = (k1 - k0) / (k0 + k1);
        z = (ratio < SPACING_RATIO ? SPACING_RATIO / ratio : ratio / SPACING_RATIO);
        if (zvalue == -1 || z < zvalue) {
          zvalue = z;
          best_spc = spc;
        }
      }
      w_total = (cols * bw + (cols - 1) * best_spc);
      h_total = (rows * bh + (rows - 1) * best_spc);
      if (w_total <= W_MAX && h_total <= H_MAX) {
        break;
      }
    }
    width = bw;
    height = bh;
    text_scale = size;
    spacing = best_spc;
  } else if (style == 'list') {
    dir = 'vert';
    var margins = [BUFFER_MARGIN, override.listStretch ? BUFFER_MARGIN : '*', BUFFER_MARGIN, '*'];

    //layout priority: maximize button size
    fits = false;
    for (size = MAX_TEXT_SIZE_LIST; size >= MIN_TEXT_SIZE; size -= .1) {
      var ext = buttonDimensions(getChoiceExtent(longest_choice, size, multi));
      bw = ext[0];
      bh = ext[1];
      spc = Math.max(Math.round(bh * .1), 5);

      rows = Math.floor((H_MAX + spc) / (bh + spc));
      cols = Math.ceil(choices.length / rows)
        w_total = (cols * bw + (cols - 1) * spc);
      h_total = (rows * bh + (rows - 1) * spc);
      if (w_total <= W_MAX && h_total <= H_MAX) {
        fits = true;
        break;
      }
    }
    if (!fits) {
      throw new Error("choices too numerous or verbose to fit!");
    }

    width = (override.listStretch ? '*' : bw);
    height = bh;
    text_scale = size;
    spacing = spc;
  }

  return {style: style, nrows: rows, ncols: cols, width: width, height: height, spacing: spacing, dir: dir, textscale: text_scale, margins: margins};
}

function getChoiceExtent (text, size, multi, bounding_width) {
  //increase text length to account for checkbox
  return getTextExtent((multi ? '\u2610 ' : '') + text, size, bounding_width);
}

function getTextExtent (text, size, bounding_width) {
  if (bounding_width == null) {
    bounding_width = $('#staging')[0].clientWidth;
  }

  var snippet_container = document.getElementById('snippet_container');
  var snippet = document.getElementById('snippet');

  snippet_container.style.width = bounding_width + 'px';
  snippet.textContent = text;
  snippet.style.fontSize = (100. * size) + '%';
  return [snippet.offsetWidth, snippet.offsetHeight];
}

function buttonDimensions (textdim) {
  return [Math.round(1.1 * textdim[0] + 0.7 * textdim[1]), Math.round(textdim[1] * 1.5)];
}

function render_button_grid (layout_params, choices, values, multi, selected, onclick, style) {
  var buttons = generate_choice_buttons(choices, values, multi, selected, layout_params, onclick, style);

  var button_grid = [];
  for (var i = 0; i < layout_params.nrows * layout_params.ncols; i++) {
    var c = i % layout_params.ncols;
    var r = (i - c) / layout_params.ncols;
    var j =  (layout_params.dir == 'horiz' ? layout_params.ncols * r + c : layout_params.nrows * c + r);
    button_grid.push(j < choices.length ? buttons[j] : null);
  }

  layout_info = new Layout({id: 'ch',
                            nrows: layout_params.nrows,
                            ncols: layout_params.ncols,
                            widths: layout_params.width,
                            heights: layout_params.height,
                            margins: layout_params.margins,
                            spacings: layout_params.spacing,
                            content: button_grid});
  return {layout: layout_info, buttons: buttons};
}

function generate_choice_buttons (choices, values, multi, selected, layout_params, onclick, style) {
  selected = norm_selected(selected);
  var buttons = [];
  for (var i = 0; i < choices.length; i++) {
    var value = (values == null ? i + 1 : values[i]);
    var isSelected = (selected != null && selected.indexOf(value) != -1);
    var button_info = {label: choices[i], value: value, selected: isSelected};
    buttons.push(button_info);
  }

  var params = style || {};
  params.textsize = layout_params.textscale;
  params.action = onclick;
  params.centered = layout_params.style == 'grid';
  params.multi = multi;
  return btngrid(buttons, params);
}

function uid (id) {
  if (id == null || id == '')
    id = "id-" + Math.floor(Math.random() * 1000000000);
    return id;
}

function new_div (id, top, left, width, height) {
  var div = document.createElement("div");
  div.id = uid(id);
  div.style.position = 'absolute';
  div.style.top = top + "px";
  div.style.left = left + "px";
  div.style.width = width + "px";
  div.style.height = height + "px";
  return div;
}

function endswith (x, suffix) {
  var sx = String(x);
  return sx.substring(sx.length - suffix.length) == suffix;
}

function partition (p) {
  //try to catch bug from swapping display widgets out of order (alternative to fixing the bug more deeply)
  if (p.pane_width == 0 || p.pane_height == 0) {
    console.log('debug: pane dimensions are zero (' + p.pane_width + ', ' + p.pane_height + '); this means you are \
probably updating an Indirect widget that is not currently on-screen; re-order your rendering calls');
  }

  var EPSILON = 1.0e-3;

  //create partitions
  var make_partitions = function (cells, margin_lo, margin_hi, spacing) {
    var sizes = new Array();
    var count = 2*cells.length + 1;
    for (var i = 0; i < count; i++) {
      if (i == 0) {
        sizes[i] = margin_lo;
      } else if (i == count - 1) {
        sizes[i] = margin_hi;
      } else if (i % 2 == 0) {
        sizes[i] = spacing;
      } else {
        sizes[i] = cells[(i - 1) / 2];
      }
    }
    return sizes;
  }
  var hSizes = make_partitions(p.widths, p.lmargin, p.rmargin, p.hspacing);
  var vSizes = make_partitions(p.heights, p.tmargin, p.bmargin, p.vspacing);

  //normalize raw pixel values
  var px_norm = function (sizes) {
    for (var i = 0; i < sizes.length; i++) {
      var val = sizes[i] + '';
      if (val.indexOf('@') == -1 && val.indexOf('*') == -1 && val.indexOf('%') == -1) {
        sizes[i] = parseFloat(val);
      }
    }
  }
  px_norm(hSizes);
  px_norm(vSizes);

  //normalize percentage-based widths
  var pct_norm = function (sizes, pane_dim, screen_dim) {
    var avg_size = Math.sqrt(p.pane_width * p.pane_height);
    var min_size = Math.min(p.pane_width, p.pane_height);
    var max_size = Math.max(p.pane_width, p.pane_height);
    var abs_avg_size = Math.sqrt(p.screen_width * p.screen_height);
    var abs_min_size = Math.min(p.screen_width, p.screen_height);
    var abs_max_size = Math.max(p.screen_width, p.screen_height);

    for (var i = 0; i < sizes.length; i++) {
      var d = sizes[i] + '';
      if (d.indexOf('%') != -1) {
        var pct = parseFloat(d.substring(0, d.indexOf('%'))) / 100.;
        if (endswith(d, '-')) {
          var total = min_size;
        } else if (endswith(d, '+')) {
          var total = max_size;
        } else if (endswith(d, '=')) {
          var total = avg_size;
        } else if (endswith(d, '-!')) {
          var total = abs_min_size;
        } else if (endswith(d, '+!')) {
          var total = abs_max_size;
        } else if (endswith(d, '=!')) {
          var total = abs_avg_size;
        } else if (endswith(d, '!')) {
          var total = screen_dim;
        } else {
          var total = pane_dim;
        }

        sizes[i] = total * pct;
      }
    }
  }
  pct_norm(hSizes, p.pane_width, p.screen_width);
  pct_norm(vSizes, p.pane_height, p.screen_height);

  var extract_proportions = function (sizes, c, total_size) {
    var proport = new Array();
    var sum_proport = 0.;
    var sum_alloc = 0;
    for (var i = 0; i < sizes.length; i++) {
      if (endswith(sizes[i], c)) {
        var sfactor = sizes[i].substring(0, sizes[i].length - 1);
        var prop = (sfactor.length > 0 ? parseFloat(sfactor) : 1.);
        proport.push(prop);
        sum_proport += prop;
      } else {
        proport.push(-1);
        if (!isNaN(sizes[i])) {
          sum_alloc += sizes[i];
        }
      }
    }
    if (sum_alloc > total_size + EPSILON) {
      throw new Error('inconsistent dimension spec for layout; too big for allowed size');
    }
    return {psizes: proport, propsum: sum_proport, allocsum: sum_alloc};
  }

  var set_prop_sizes = function (sizes, propsizes, unitsize) {
    for (var i = 0; i < sizes.length; i++) {
      if (propsizes[i] != -1) {
        sizes[i] = propsizes[i] * unitsize;
      }
    }
  }

  //normalize aspect-locked proportial widths
  var haprop = extract_proportions(hSizes, '@', p.pane_width);
  var vaprop = extract_proportions(vSizes, '@', p.pane_height);
  //  determine size of '@'
  var asize = Math.min((p.pane_width - haprop.allocsum) / haprop.propsum,
                       (p.pane_height - vaprop.allocsum) / vaprop.propsum);
  set_prop_sizes(hSizes, haprop.psizes, asize);
  set_prop_sizes(vSizes, vaprop.psizes, asize);

  //normalize leftover proportional widths
  var hprop = extract_proportions(hSizes, '*', p.pane_width);
  var vprop = extract_proportions(vSizes, '*', p.pane_height);
  set_prop_sizes(hSizes, hprop.psizes, (p.pane_width - hprop.allocsum) / hprop.propsum);
  set_prop_sizes(vSizes, vprop.psizes, (p.pane_height - vprop.allocsum) / vprop.propsum);

  //check that all space consumed
  var check_size_used = function (sizes, ttl_size) {
    var sum = 0;
    for (var i = 0; i < sizes.length; i++) {
      sum += sizes[i];
    }
    if (sum < ttl_size - EPSILON) {
      throw new Error('inconsistent dimension spec for layout; not all space consumed');
    }
  }
  check_size_used(hSizes, p.pane_width);
  check_size_used(vSizes, p.pane_height);

  //distribute rounding error
  var round_sizes = function(sizes) {
    var sum0 = 0;
    var fsum0 = 0;
    for (var i = 0; i < sizes.length; i++) {
      var fsum1 = fsum0 + sizes[i];
      var sum1 = Math.round(fsum1);
      sizes[i] = sum1 - sum0;
      fsum0 = fsum1;
      sum0 = sum1;
    }
  }
  round_sizes(hSizes);
  round_sizes(vSizes);

  console.log(hSizes, vSizes, p.id);
  return [hSizes, vSizes];
}

function offsets (dims) {
  var off = 0;
  var offs = new Array();
  for (var i = 0; i < dims.length; i++) {
    offs.push(off);
    off += dims[i];
  }
  return offs;
}

function set_color (elem, color, fallback_color) {
  var _color = (color != null && color != '' ? color : fallback_color);
  if (_color == null) {
    elem.style.background = null;
    elem.style.backgroundColor = null;
  } else {
    if (_color.substring(0, 2) == 'gr') {
      var pcs = _color.split(' ');
      if (supportsGradient()) {
        elem.style.backgroundColor = null;
        var _bg = null;
        if (jQuery.browser.mozilla) {
          _bg = '-moz-linear-gradient(top, ' + pcs[1] + ' 0%, ' + pcs[2] + ' 100%)';
        } else if (jQuery.browser.webkit) {
          _bg = '-webkit-gradient(linear, left top, left bottom, color-stop(0%, ' + pcs[1] + '), color-stop(100%, ' + pcs[2] + '))'; 
        } else {
          //is there a css standard?
        }
        elem.style.background = _bg;
        return;
      } else {
        _color = ainv(pcs, -1);
      }
    }
    elem.style.background = null;
    elem.style.backgroundColor = _color;
  }
}

function ainv (arr, i) {
  return arr[arr.length - Math.abs(i)];
}

function Top (main, overlay) {
  this.main = main;
  this.overlay = overlay;
  this.waitdiv = null;

  this.render = function (parent_div) {
    var maindiv = new_div('main', 0, 0, parent_div.clientWidth, parent_div.clientHeight);
    parent_div.appendChild(maindiv);
    this.main.render(maindiv);
    
    if (this.overlay != null) {
      var ovdiv = new_div('overlay', 0, 0, parent_div.clientWidth, parent_div.clientHeight);
      parent_div.appendChild(ovdiv);  
      this.overlay.render(ovdiv);
    }

    this.waitdiv = document.createElement('div');
    this.waitdiv.style.position = 'absolute';
    this.waitdiv.style.display = 'none';
    this.waitdiv.style.width = '100%';
    this.waitdiv.style.height = parent_div.clientHeight + 'px';
    this.waitdiv.style.zIndex = 1000;
    this.waitdiv.innerHTML = '<div style="background: #fff; opacity: .7; height: 100%;"></div><div style="position: absolute; top: 150px; width: 100%; text-align: center; font-weight: bold; font-size: 200%; color: #222;">Please wait&hellip;<br><br><img src="' + STATIC_MEDIA_URL + 'formplayer/img/loading.png"></div><div id="abort-popup" style="display: none; position: absolute; left: 40px; bottom: 40px;"><p style="max-width: 35em; font-size: medium; font-weight: bold;">This is taking a long time. There might be a problem. You can click the ABORT button to go back to the main screen, but you will lose the form you were working on if you do.</p>' + oneOffButtonHTML ('abort', 'ABORT') + '</div>';
    parent_div.appendChild(this.waitdiv);
    setClickEvent($('#abort')[0], function () { window.location = FORCE_ABORT_URL; });
  }

  this.abortTimer = null;
  this.showWaiting = function (active) {
    if (active) {
      if (this.abortTimer) {
        clearTimeout(this.abortTimer);
      }
      $('#abort-popup')[0].style.display = 'none';
      this.abortTimer = setTimeout(function () {
          enableInput(true);
          $('#abort-popup')[0].style.display = 'block';
        }, 30000);
    }
    this.waitdiv.style.display = (active ? 'block' : 'none');
  }
}

function htmlescape (raw) {
  raw = raw.replace(/&/g, '&amp;');
  raw = raw.replace(/</g, '&lt;');
  raw = raw.replace(/>/g, '&gt;');
  raw = raw.replace(/\'/g, '&apos;');
  raw = raw.replace(/\"/g, '&quot;');
  return raw;
}

function Overlay (bg_color, fadeout) {
  this.bg_color = bg_color;
  this.fadeout = fadeout * 1000.;

  this.mask_color = null;
  this.text = '';
  this.timeout = null;
  this.ondismiss = null;
  this.choices = null;
  this.actions = null;

  this.active = null;  
  this.container = null;
  this.timeout_id = null;
  this.span = null;
  this.mask = null;

  this.setTimeout = function (to) {
    this.timeout = to * 1000.;
  }

  this.activate = function (args) {
    this.setMaskColor(args.color);
    this.setTimeout(args.timeout || 0.);
    this.ondismiss = args.ondismiss;
    this.setText(args.text || '', args.choices, args.actions);
    this.setActive(true);
  }

  this.setActive = function (state, manual) {
    if (this.active && state) {
      return; //do nothing if already active
    }
    
    this.active = state;
      
    if (state) {
      this.container.style.display = 'block';
      if (this.timeout != null && this.timeout > 0) {
        var self = this;
        this.timeout_id = setTimeout(function () {
          self.timeout_id = null;
          if (self.fadeout != null && self.fadeout > 0) {
            $(self.container).fadeOut(self.fadeout, function () {self.setActive(false);});
          } else {
            self.setActive(false);
          } 
        }, this.timeout);
      }
    } else {
      if (manual)
        $(this.container).stop(true, true);
      this.container.style.display = 'none';
      if (this.timeout_id != null)
        clearTimeout(this.timeout_id);
      if (this.ondismiss) {
        this.ondismiss();
      }
    } 
  }
  
  this.setText = function (text, choices, actions) {
    this.text = text;
    this.choices = choices;
    this.actions = actions;

    if (this.span != null)
      this.renderContent();
  }
  
  this.setMaskColor = function (color) {
    this.mask_color = color;
    if (this.mask != null)
      this.mask.style.backgroundColor = color;
  }
  
  this.renderContent = function () {
    var content = htmlescape(this.text);

    if (!this.choices)
      this.choices = [];

    if (this.choices.length > 0) {
      content += '<br><br>';
      for (var i = 0; i < this.choices.length; i++) {
        content += oneOffButtonHTML('alert-ch' + i, this.choices[i], this.choices.length == 1 ? 'center' : null, null, 'margin-bottom: 5px;');
      }
    }

    this.span.innerHTML = content;

    if (this.choices.length > 0) {
      for (var i = 0; i < this.choices.length; i++) {
        setClickEvent($('#alert-ch' + i)[0], this.actionable(i));
      }
      setClickEvent(this.container, null);
    } else {
      var self = this;
      setClickEvent(this.container, function () { self.setActive(false, true); });
    }
  }

  this.actionable = function (i) {
    var self = this;
    return function () {
      self.ondismiss = self.actions[i];
      self.setActive(false, true);
    };
  }

  this.render = function (parent_div) {
    this.container = parent_div;
  
    mask = new_div('mask', 0, 0, parent_div.clientWidth, parent_div.clientHeight);
    mask.style.backgroundColor = this.mask_color;
    mask.style.opacity = .7;
    parent_div.appendChild(mask);
    this.mask = mask;
    
    content = document.createElement('div');
    content.style.position = 'relative';
    content.style.top = '175px';
    content.style.width = '70%';
    content.style.marginLeft = 'auto';
    content.style.marginRight = 'auto';
    
    span = document.createElement('div');
    span.id = 'overlay-content';
    span.style.border = '3px solid black';
    span.style.padding = '20px';
    span.style.backgroundColor = this.bg_color;
    //god damnit css!!!
    this.span = span;

    content.appendChild(span);
    parent_div.appendChild(content);
    this.renderContent();
    
    this.setActive(false);
  }
}

function oneOffButtonHTML (id, text, align, padding, custom_style) {
  padding = padding || 7;
  custom_style = custom_style || '';

  return '<table class="shiny-button rounded" id="' + id + '" ' + (align ? 'align="' + align + '" ' : '') + 'cellpadding="' + padding + '" style="color: white; font-weight: bold; ' + custom_style + '"><tr><td><strong>&nbsp;' + htmlescape(text) + '&nbsp;</strong></td></tr></table>';
}

function InputArea (args) {
  this.id = args.id;
  this.border = args.border;
  this.border_color = args.border_color || '#000';
  this.padding = args.padding || 0;
  this.inside_color = args.inside_color || '#fff';
  this.child = args.child;
  this.onclick = args.onclick;
  this.bglabel = args.label;

  this.layout;
  this.container = null;

  //yikes! this didn't turn out that well
  this.setBgColor = function (bg_color) {
    this.inside_color = bg_color;
    if (this.container) {
      if (this.padding > 0) {
        this.layout.child_index[0].style.backgroundColor = bg_color;
        this.layout.content[0].child_index[0].style.backgroundColor = bg_color;
      } else {
        this.layout.child_index[0].style.backgroundColor = bg_color;
      }
      if (this.child instanceof TextInput) {
        this.child.control.style.backgroundColor = bg_color;
      }
    }
  }
  
  this.setText = function (text) {
    //kind of hacky
    var elem = $('#' + this.id + ' span')[0];
    if (elem != null) {
      elem.style.opacity = (!text ? .1 : 1.);
    }

    text = text || this.bglabel || '';
    this.child.setText(text);
  }
  
  this.setMaxLen = function (maxlen) {
    this.child.setMaxLen(maxlen);
  }

  this.render = function (parent_div) {
    if (this.padding > 0) {
      inside = new Layout({id: this.id + '-padded', margins: this.padding, content: [this.child]});
    } else {
      inside = this.child;
    }
    this.layout = new Layout({id: this.id, margins: this.border, color: this.inside_color, margin_color: this.border_color, content: [inside]});
    this.layout.render(parent_div);
    this.container = this.layout.container;
    setClickEvent(this.container, this.onclick);
  }
}

function CustomContent (id, content) {
  this.id = id;
  this.content = content;

  this.container = null;

  this.render = function (parent_div) {
    this.container = parent_div;
    parent_div.innerHTML = this.content;
  }
}

function cmp (a, b) {
  return (a > b ? 1 : (a < b ? -1 : 0));
}

function cmp_arr (a, b) {
  for (var i = 0; i < Math.min(a.length, b.length); i++) {
    var c = cmp(a[i], b[i]);
    if (c != 0) {
      return c;
    }
  }
  return cmp(a.length, b.length);
}

function supportsGradient () {
  if (jQuery.browser.mozilla) {
    return cmp_arr(jQuery.browser.version.split('.'), [1, 9, 2]) >= 0;
  } else if (jQuery.browser.webkit) { //all versions support it?
    return true;
  } else {
    return true; //hope for the best
  }
}

function isEventSupported(eventName) {
  var element = document.createElement('div');
  var eventName = 'on' + eventName;
  
  var isSupported = (eventName in element);
  if (!isSupported) {
    if (element.setAttribute) {
      element.setAttribute(eventName, function () {});
      isSupported = (typeof element[eventName] == 'function');
    }
  }
  return isSupported;
}

function isMobileDevice () {
  //alternatively, we could check user agent string for any of: android, iphone, ipad, ipod, mobile
  return isEventSupported('touchstart');
}

function setClickEvent (obj, handler) {
  if (clickOnMouseDown()) {
    if (isMobileDevice()) {
      obj.ontouchstart = handler;
    } else {
      obj.onmousedown = handler;
    }
  } else {
    obj.onclick = handler;
  }
}