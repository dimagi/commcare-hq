

SCREEN_BORDER = '1.1%=!'; //10px @ 1024x768;
SCREEN_MARGIN = '1.1%=!'; //10px @ 1024x768;
SECTION_MARGIN = '0.68%=!';
HEADER_HEIGHT = '8%!';
FOOTER_HEIGHT = '10%!';
FOOTER_BUTTON_WIDTH = '15%!';
FOOTER_BUTTON_SPACING = SECTION_MARGIN;
HELP_BUTTON_SPACING = SECTION_MARGIN;

BORDER_COLOR = '#000';
MAIN_COLOR = '#eef';
HEADER_COLOR = '#dde';
FOOTER_COLOR = '#abd';
BUTTON_TEXT_COLOR = '#fff';
TEXT_COLOR = '#000';
KEYBUTTON_COLOR = '#118';
KEYBUTTON_CLASS = 'key-button';
BUTTON_SELECTED_COLOR = '#0bf';
BUTTON_DISABLED_COLOR = '#888';
HIGHLIGHT_COLOR = '#ffc';
NUMPAD_COLOR = '#16c';
NUMPAD_CLASS = 'numpad-button';
SPC_COLOR = '#aef';
SPC_CLASS = 'spacebar';
BACKSPACE_COLOR = '#999';
BACKSPACE_CLASS = 'clear-button';

HELP_BGCOLOR = '#6d6';
ERR_BGCOLOR = '#d66';
ALERT_BGCOLOR = '#dd6';

AUTO_ADVANCE_DELAY = 150; //ms
KEYFLASH = 150; //ms
ADVANCE_LOCKOUT = 800; //ms

function initStaticWidgets () {
  questionCaption = new TextCaption({id: 'q-caption', color: TEXT_COLOR, align: 'left', valign: 'top'});

  TactileButton = function (args) {
    var action = args.action;
    this.activectr = 0;
    var self = this;
    args.action = function (ev, c, button) {
      if (self.activectr == 0) {
        button.flash(KEYFLASH);
        action();
      }
    }

    inherit(this, new ChoiceButton(args));

    this.activate = function () {
      this.activectr--;
      if (this.activectr < 0) {
        this.activectr = 0;
      }
    }

    this.deactivate = function () {
      this.activectr++;
    }
  }

  nextButton = new TactileButton({id: 'next-button', color: '#1a3', selcolor: '#8f8', textcolor: BUTTON_TEXT_COLOR, label: 'NEXT', textsize: 1.2, action: nextClicked});
  backButton = new TactileButton({id: 'back-button', color: '#6ad', selcolor: '#7df', textcolor: BUTTON_TEXT_COLOR, label: 'BACK', textsize: .9, action: backClicked});
  helpButton = new TextButton({id: 'help-button', color: '#aaa', textcolor: BUTTON_TEXT_COLOR, caption: '?', textsize: 1., onclick: helpClicked});
  homeButton = new TextButton({id: 'home-button', color: '#d23', textcolor: BUTTON_TEXT_COLOR, caption: 'HOME', textsize: .9, onclick: homeClicked});
  
  questionEntry = new Indirect();
  
  overlay = new Overlay(HEADER_COLOR, 2.);
  touchscreenUI = new Top(
    // main content
    new Layout({id: 'main', nrows: 3, heights: [HEADER_HEIGHT, '*', FOOTER_HEIGHT], margins: SCREEN_BORDER, color: MAIN_COLOR, margin_color: BORDER_COLOR, content: [
      new Layout({id: 'header', margins: [SCREEN_MARGIN, SCREEN_MARGIN, SCREEN_MARGIN, SECTION_MARGIN], color: HEADER_COLOR, margin_color: '-', content: [
        new Layout({id: 'top-bar', ncols: 2, widths: ['*', '1.1@'], heights: '@', spacings: HELP_BUTTON_SPACING, content: [
          questionCaption,
          helpButton
        ]})
      ]}),
      new Layout({id: 'entry', margins: [SCREEN_MARGIN, 0], content: [questionEntry]}),
      new Layout({id: 'footer', ncols: 4, widths: [FOOTER_BUTTON_WIDTH, FOOTER_BUTTON_WIDTH, '*', FOOTER_BUTTON_WIDTH], 
                 margins: [SCREEN_MARGIN, SCREEN_MARGIN, SECTION_MARGIN, SCREEN_MARGIN], spacings: FOOTER_BUTTON_SPACING, color: FOOTER_COLOR, margin_color: '-', spacing_color: '-', content: [
        backButton, 
        homeButton,
        null, // progress bar 
        nextButton
      ]}),
    ]})
  ,
    //notifications overlay
    overlay
  );

  answerBar = new Indirect();
  freeEntryKeyboard = new Indirect();
  freeEntry = new Layout({id: 'free-entry', nrows: 2, heights: ['18%', '*'], content: [
    answerBar,
    new Layout({id: 'kbd', margins: ['1.5%=', '1.5%=', 0, '.75%='], content: [freeEntryKeyboard]})
  ]});
}

BKSP = '_del';
backspaceKey = {label: '\u21d0', value: BKSP, style: BACKSPACE_CLASS, color: BACKSPACE_COLOR};
hyphenKey = {label: '\u2013', value: '-'};
spaceKey = {label: '\u2423', value: ' ', style: SPC_CLASS, color: SPC_COLOR};

function makeNumpad (extraKey, action) {
  return aspect_margin('1.7%-',
    new Layout({id: 'numpad', nrows: 4, ncols: 3, widths: '7@', heights: '7@', margins: '*', spacings: '@', 
                content: btngrid(['1', '2', '3', '4', '5', '6', '7', '8', '9', extraKey, '0', backspaceKey], {textsize: 2., action: action})})
  );
}

function makeKeyboard (full, action, style) {
  if (qwertyKbd()) {
    kbdFull = [
      'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', {label: '7', style: NUMPAD_CLASS}, {label: '8', style: NUMPAD_CLASS}, {label: '9', style: NUMPAD_CLASS},
      'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', '?', {label: '4', style: NUMPAD_CLASS}, {label: '5', style: NUMPAD_CLASS}, {label: '6', style: NUMPAD_CLASS},
      'Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '!', {label: '1', style: NUMPAD_CLASS}, {label: '2', style: NUMPAD_CLASS}, {label: '3', style: NUMPAD_CLASS},
      hyphenKey, '+', '%', '&', '*', '/', ':', ';', '(', ')', spaceKey, {label: '0', style: NUMPAD_CLASS}, backspaceKey     
    ];
    kbdAlpha = [
      'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P',
      'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', backspaceKey,
      'Z', 'X', 'C', 'V', 'B', 'N', 'M', hyphenKey, '\'', spaceKey
    ];
  } else {
    kbdFull = [
      'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', {label: '7', style: NUMPAD_CLASS}, {label: '8', style: NUMPAD_CLASS}, {label: '9', style: NUMPAD_CLASS}, backspaceKey,
      'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', {label: '4', style: NUMPAD_CLASS}, {label: '5', style: NUMPAD_CLASS}, {label: '6', style: NUMPAD_CLASS}, '.',
      'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', spaceKey, {label: '1', style: NUMPAD_CLASS}, {label: '2', style: NUMPAD_CLASS}, {label: '3', style: NUMPAD_CLASS}, ',',
      hyphenKey, '+', '%', '&', '*', '/', ':', ';', '(', ')', {label: '0', style: NUMPAD_CLASS}, '!', '?'     
    ];
    kbdAlpha = [
      'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', backspaceKey,
      'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', spaceKey,
      'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', hyphenKey, '\''
    ];
  }
  kbdAlphaCondensed = [
    'A', 'B', 'C', 'D', 'E', backspaceKey,
    'F', 'G', 'H', 'I', 'J', spaceKey,
    'K', 'L', 'M', 'N', 'O', hyphenKey, 
    'P', 'Q', 'R', 'S', 'T', '\'',
    'U', 'V', 'W', 'X', 'Y', 'Z'
  ];

  if (full) {
    return new Layout({id: 'text-kbd', nrows: 4, ncols: 13, widths: '4@', heights: '5@', margins: '*', spacings: '0.36@', content: btngrid(kbdFull, {textsize: 1.4, action: action})});
  } else if (style == 'condensed') {
    return new Layout({id: 'text-kbd', nrows: 3, ncols: 10, widths: '4@', heights: '7@', margins: '*', spacings: '0.36@', content: btngrid(kbdAlpha, {textsize: 1.4, action: action})});
  } else if (style == 'supercondensed') {
    return new Layout({id: 'text-kbd', nrows: 5, ncols: 6, widths: '5@', heights: '5@', margins: '*', spacings: '0.36@', content: btngrid(kbdAlphaCondensed, {textsize: 1.8, action: action})});
  } else {
    return new Layout({id: 'text-kbd', nrows: 3, ncols: 10, widths: '4@', heights: '5@', margins: '*', spacings: '0.36@', content: btngrid(kbdAlpha, {textsize: 1.9, action: action})});
  }
}

//append a 'clear' button to input field(s) and size appropriately
function make_answerbar (content, widths, id) {
  if (!(content instanceof Array)) {
    content = [content];
  }
  if (!(widths instanceof Array)) {
    widths = [widths];
  }
  
  //todo: find a way to generalize this?
  var expands = false;
  for (var i = 0; i < widths.length; i++) {
    if (widths[i].indexOf('*') != -1) {
      expands = true;
      break;
    }
  }
  
  var clearButton = new TactileButton({id: 'clear-button', color: '#aaa', selcolor: '#ddd', textcolor: BUTTON_TEXT_COLOR, label: 'CLEAR', textsize: 0.8, action: clearClicked});
  content.push(clearButton);
  widths.push('1.7@');
  
  return new Layout({margins: ['3%', '18%'], content: [
      new Layout({id: id, ncols: content.length, heights: '@', widths: widths, margins: [expands ? 0 : '*', '*'], spacings: '.08@', content: content})
    ]});
}

function make_date_fields (datecontext) {
  return {
    d: new InputArea({id: 'dayinp', label: 'd', border: 3, child: new TextCaption({color: TEXT_COLOR, size: 1.6}), onclick: function () {datecontext.goto_('day');}}),
    m: new InputArea({id: 'monthinp',  label: 'm', border: 3, child: new TextCaption({color: TEXT_COLOR, size: 1.6}), onclick: function () {datecontext.goto_('month');}}),
    y: new InputArea({id: 'yearinp',  label: 'y', border: 3, child: new TextCaption({color: TEXT_COLOR, size: 1.6}), onclick: function () {datecontext.goto_('year');}}),
  }; 
}

function make_date_answerbar (datefields) {
  var dateSpacer = function () { return new TextCaption({color: TEXT_COLOR, caption: '\u2013', size: 1.7}); };

  var content = [];
  var widths = [];
  for (var i = 0; i < 3; i++) {
    var field = dateDisplayOrder()[i];
    if (field == 'd') {
      content.push(datefields.d);
      widths.push('1.3@');
    } else if (field == 'm') {
      content.push(datefields.m);
      widths.push(numericMonths() ? '1.3@' : '1.85@');
    } else if (field == 'y') {
      content.push(datefields.y);
      widths.push('2.3@');
    }
    
    if (i < 2) {
      content.push(dateSpacer());
      widths.push('.5@');
    }
  }
  
  return make_answerbar(content, widths, 'date-bar');
}

function setting (varname, defval) {
  var val = window[varname];
  return (val != null ? val : defval);
}

function numericMonths () {
  return setting('NUMERIC_MONTHS', false);
}

function qwertyKbd () {
  return setting('KBD_QWERTY', false);
}

function autoAdvance () {
  return setting('AUTO_ADVANCE', true);
}

function dateDisplayOrder () {
  return setting('DATE_DISPLAY_ORDER', 'ymd');
}

function dateEntryOrder () {
  var val = setting('DATE_ENTRY_ORDER', '-');
  return (val == '-' ? dateDisplayOrder() : val);
}

function clickOnMouseDown () {
  return setting('CLICK_MOUSEDOWN', true);
}

function autoCompleteStyle () {
  return setting('AUTOCOMPLETE_STYLE', 'inline');
}

function autoCompleteCurrentTextAsSuggestion () {
  return setting('AUTOCOMPL_CURRENT_TEXT_AS_SUGGESTION', true);
}

function autoCompleteKeyboardHints () {
  return setting('AUTOCOMPL_KEYBOARD_HINTS', true);
}

function xformAreYouDone () {
  return setting('XFORM_ARE_YOU_DONE', true);
}

function showAlertsOnBack () {
  return setting('SHOW_ALERTS_ON_BACK', false);
}

var clicksEnabled;
var clickDisableCounter = 0;
function setup (fullscreen) {
  if (fullscreen) {
    $('#viewport')[0].style.width = window.innerWidth + 'px';
    $('#viewport')[0].style.height = window.innerHeight + 'px';
    console.log('setting to window dimensions ' + window.innerWidth + ', ' + window.innerHeight);
  }
  SCREEN_WIDTH = $('#viewport')[0].clientWidth;
  SCREEN_HEIGHT = $('#viewport')[0].clientHeight;

  $('#staging')[0].style.top = (SCREEN_HEIGHT + 500) + 'px';
  $('#staging')[0].style.width = (1.5 * SCREEN_WIDTH) + 'px';
  $('#staging')[0].style.height = '600px';

  clicksEnabled = true;
  $('body')[0].addEventListener(clickOnMouseDown() ? 'mousedown' : 'click', function (ev) {
      if (!clicksEnabled) {
        ev.stopPropagation();
        return false; 
      } else {
        return true;
      }
    }, true);

  //shortcuts
  var shortcut_args = {'type': 'keydown', 'propagate': false, 'target': document};
  shortcut.add("Alt+N", function() { answerQuestion(); }, shortcut_args);
  shortcut.add("Alt+P", function() { prevQuestion(); }, shortcut_args);
  shortcut.add("esc", function() { overlay.setActive(false); }, shortcut_args);
}

function disableInput() {
  clicksEnabled = false;
  clickDisableCounter++;
}

function enableInput(force) {
  clickDisableCounter--;

  if (clickDisableCounter < 0 || force) {
    clickDisableCounter = 0;
  }

  if (clickDisableCounter == 0) {
    clicksEnabled = true;
  }
}

function helpClicked () {
  activeControl.help();
}

function backClicked () {
  activeControl.back();
}

function homeClicked (ev, x) {
  captions = gFormAdapter.quitWarning();

  showActionableAlert(captions.main,
                      [captions.quit, captions.cancel],
                      [function () {goHome();}, null]);
}

function goHome () {
  if (gFormAdapter.abort) {
    gFormAdapter.abort();
  } else {
    //console.log('warning: workflow has no abort() method; returning to root page');
    location.href='/';
  }
}

function nextClicked () {
  activeControl.next();
}

function clearClicked (ev, x) {
  activeControl.clear();
}

function autoAdvanceTrigger () {
  if (autoAdvance()) {
    disableInput();
    nextButton.flash(AUTO_ADVANCE_DELAY + KEYFLASH);
    setTimeout(function () {
        nextClicked();
        nextButton.deactivate();
        setTimeout(function () {
            nextButton.activate();
          }, ADVANCE_LOCKOUT);

        enableInput();
      }, AUTO_ADVANCE_DELAY);
  }
}

function showError (text) {
  overlay.activate({
      text: text,
      color: ERR_BGCOLOR,
      timeout: 3.,
    });
}

function showAlert (text, ondismiss) {
  overlay.activate({
      text: text,
      color: ALERT_BGCOLOR,
      ondismiss: ondismiss
    });
}

function showActionableAlert (text, choices, actions) {
  overlay.activate({
      text: text,
      choices: choices,
      actions: actions,
      color: ALERT_BGCOLOR
    });
}

function confirmDone (doneFunc) {
  disableInput();
  setTimeout(function () { enableInput(); }, ADVANCE_LOCKOUT);
  showActionableAlert('The form is finished. If you made any mistakes, GO BACK and make changes. SUBMIT the form when you are done. You can\'t make any more changes after you submit the form.',
                      ['SUBMIT', 'GO BACK and make changes'],
                      [doneFunc, backClicked]);
}

function ajaxActivate() {
  disableInput();
  var waitingTimer = setTimeout(function () { touchscreenUI.showWaiting(true); }, 300);
  
  return function() {
    enableInput();
    clearTimeout(waitingTimer);
    touchscreenUI.showWaiting(false);
  };
}

function make_button (label, args) {
  args.color = args.color || KEYBUTTON_COLOR;
  args.style = args.style || KEYBUTTON_CLASS;
  args.textcolor = args.textcolor || BUTTON_TEXT_COLOR;
  args.selcolor = args.selcolor || BUTTON_SELECTED_COLOR;
  args.inactcolor = args.inactcolor || BUTTON_DISABLED_COLOR;
  args.label = label;

  return new ChoiceButton(args);
}
  
/* utility function to generate a grid array of buttons */
function btngrid (buttons_info, template) {
  var content = [];
  for (var i = 0; i < buttons_info.length; i++) {
    var buttonspec = buttons_info[i];
    if (buttonspec != null) {
      var args = {};
      for (var key in template) {
        args[key] = template[key];
      }
      if (buttonspec instanceof Object) {
        for (var key in buttonspec) {
          args[key] = buttonspec[key];
        }
        var label = buttonspec.label;
      } else {
        var label = buttonspec;
      }
      var button = make_button(label, args);
      if (args.selected) {
        button.setStatus('selected');
      }
    } else {
      var button = null;
    }
    content.push(button); 
  }
  return content;
}

function aspect_margin (margin, inner) {
  return new Layout({margins: margin, content: [inner]});
}

function render_clean () {
  render_viewport('viewport', touchscreenUI);
}

function type_ (input_field, c, button, flash) {
  if (flash && button != null) {
    button.flash(KEYFLASH);
  }
  
  if (jQuery.browser.mozilla && jQuery.browser.version < 2) {
    // preserve firefox behavior, just send the keypress to the input
    if (c == BKSP) {
      var keyCode = 0x08;
      var charCode = 0;
    } else {
      var keyCode = 0;
      var charCode = c.charCodeAt(0);
    }

	  var evt = document.createEvent("KeyboardEvent");
	  evt.initKeyEvent("keypress", true, true, window,
	                   0, 0, 0, 0,
	                   keyCode, charCode); 
	  input_field.dispatchEvent(evt);
  } else {
    // only difference here is that the cursor is always assumed to be at the end of the input
    var elem = $(input_field);
    var prev_text = elem.val();
    if (c == BKSP) {
      if (prev_text) {
        elem.val(prev_text.substring(0, prev_text.length - 1));        
      }
    } else {
      elem.val(prev_text + c);
    }
  }
}

