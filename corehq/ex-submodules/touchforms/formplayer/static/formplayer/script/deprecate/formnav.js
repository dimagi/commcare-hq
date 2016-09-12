
function xformAjaxAdapter (formName, sessionData, savedInstance) {
  this.formName = formName;
  this.sessionData = sessionData;
  this.session_id = -1;

  this.loadForm = function (lang) {
    adapter = this;

    var preloadTags = (this.sessionData || {}).preloaders || {};
    var preload_data = {};
    for (var type in preloadTags) {
        var dict = preloadTags[type];
        preload_data[type] = {};
        for (var key in dict) {
            var val = dict[key];
            // this special character indicates a server preloader, which 
            // we make a synchronous request for
            if (val.indexOf("<") === 0) {
                valback = jQuery.ajax({url: PRELOADER_URL, type: 'GET', data:{"param": val}, async: false}).responseText;
                preload_data[type][key] = valback;
            } else {
                preload_data[type][key] = val
            }
        }
    }
    this.serverRequest(XFORM_URL, {'action': 'new-form',
                                   'form-name': this.formName,
                                   'lang': lang,
                                   'instance-content': savedInstance,
                                   'session-data': {preloaders: preload_data}},
      function (resp) {
        adapter.session_id = resp["session_id"];
        adapter._renderEvent(resp["event"], true);
      });
  }

  this.answerQuestion = function (answer) {
    adapter = this;
    if (activeQuestion["type"] == "repeat-juncture") {
      if (answer == null) {
        showError("An answer is required");
      } else if (answer.substring(0, 3) == 'rep') {
        var repIx = +answer.substring(3);
        this.serverRequest(XFORM_URL, {'action': (activeQuestion["repeat-delete"] ? 'delete-repeat' :'edit-repeat'), 
                'session-id': this.session_id, 'ix': repIx},
          function (resp) {
            adapter._renderEvent(resp["event"], true);
          });
      } else if (answer == 'add') {
        this.serverRequest(XFORM_URL, {'action': 'new-repeat', 'session-id': this.session_id},
          function (resp) {
            adapter._renderEvent(resp["event"], true);
          });
      } else if (answer == 'del') {
        activeQuestion["repeat-delete"] = true;
        this._renderEvent(activeQuestion, true);
      } else if (answer == 'done') {
        this._step(true);
      } else {
        alert('oops');
      }
    } else {
      this.serverRequest(XFORM_URL, {'action': 'answer',
                                     'session-id': this.session_id,
                                     'answer': answer},
        function (resp) {
          if (resp["status"] == "validation-error") {
            if (resp["type"] == "required") {
              showError("An answer is required");
            } else if (resp["type"] == "constraint") {
              showError(resp["reason"] || 'This answer is outside the allowed range.');      
            }
          } else {
            adapter._renderEvent(resp["event"], true);
          }
        });
    }
  }

  this.prevQuestion = function () {
    this._step(false);
  }

  this.domain_meta = function (event) {
    var meta = {};

    if (event.datatype == "date") {
      meta.mindiff = event["style"]["before"] != null ? +event["style"]["before"] : null;
      meta.maxdiff = event["style"]["after"] != null ? +event["style"]["after"] : null;
    } else if (event.datatype == "int" || event.datatype == "float") {
      meta.unit = event["style"]["unit"];
    } else if (event.datatype == 'str') {
      meta.autocomplete = (event["style"]["mode"] == 'autocomplete');
      meta.autocomplete_key = event["style"]["autocomplete-key"];
      meta.mask = event["style"]["mask"];
      meta.prefix = event["style"]["prefix"];
      meta.longtext = (event["style"]["raw"] == 'full');
    } else if (event.datatype == "multiselect") {
      if (event["style"]["as-select1"] != null) {
        meta.as_single = [];
        var vs = event["style"]["as-select1"].split(',');
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

  this._renderEvent = function (event, dirForward) {
    if (event["type"] == "question") {
      if (event["style"]["domain"])
        event["domain"] = event["style"]["domain"];
      event.domain_meta = this.domain_meta(event);

      renderQuestion(event, dirForward);
    } else if (event["type"] == "form-complete") {
      var self = this;
      var done = function () { self._formComplete(event); };

      if (xformAreYouDone()) {
        confirmDone(done);
      } else {
        done();
      }
    } else if (event["type"] == "sub-group") {
      this._step(dirForward);
    } else if (event["type"] == "repeat-juncture") {
      event["datatype"] = "select";

      var options = [];
      for (var i = 0; i < event["repetitions"].length; i++) {
        options.push({lab: event["repetitions"][i], val: 'rep' + (i + 1)});
      }

      if (!event["repeat-delete"]) {
        event["caption"] = event["main-header"];
        
        if (event["add-choice"] != null) {
          options.push({lab: event["add-choice"], val: 'add'});
        }
        if (event["del-choice"] != null) {
          options.push({lab: event["del-choice"], val: 'del'});
        }
        options.push({lab: event["done-choice"], val: 'done'});
      } else {
        event["caption"] = event["del-header"];
      }

      event["choices"] = options;
      event["answer"] = null;
      event["required"] = true;

      renderQuestion(event, dirForward);
    } else {
      alert("unrecognized event [" + event["type"] + "]");
    }
  }

  this._step = function (dirForward) {
    BACK_AT_START_ABORTS = true;

    //handle 'which repeat to delete?' interstitial
    if (!dirForward && activeQuestion["repeat-delete"]) {
      activeQuestion["repeat-delete"] = false;
      this._renderEvent(activeQuestion, false);
      return;
    }

    adapter = this;
    this.serverRequest(XFORM_URL, {'action': (dirForward ? 'next' : 'back'),
                                   'session-id': this.session_id},
      function (resp) {
        if (!dirForward && resp["at-start"] && BACK_AT_START_ABORTS) {
          adapter.abort();
        } else {
          adapter._renderEvent(resp["event"], dirForward || resp["at-start"]);
        }
      });
  }

  this._formComplete = function (params) {
    interactionComplete(function () { submit_redirect(params); });
  }

  this.abort = function () {
    interactionComplete(function () { submit_redirect({type: 'form-aborted'}); });
  }

  this.quitWarning = function () {
    return {
      'main': 'This form isn\'t finished! If you go HOME, you will throw out this form.',
      'quit': 'Go HOME; discard form',
      'cancel': 'Stay and finish form'
    }
  }

  this.serverRequest = function (url, params, callback) {
    serverRequest(
      function (cb) {
        jQuery.post(url, JSON.stringify(params), cb, "json");
      },
      callback
    );
  }
}

var requestInProgress = false;
function serverRequest (makeRequest, callback) {
  if (requestInProgress) {
    //console.log('request is already in progress; aborting');
    return;
  }
  requestInProgress = true;
  
  var ajaxDeactivate = ajaxActivate();
  makeRequest(function (resp) {
      requestInProgress = false;
      callback(resp);
      ajaxDeactivate();
    });
}

function Workflow (flow, onFinish) {
  this.flow = flow;
  this.onFinish = onFinish;
  this.data = null;

  this.start = function () {
    this.data = {}
    return this.flow(this.data);
  }

  this._finish = function () {
    this.onFinish(this.data);
  }

  this.finish = function () {
    var wf = this;
    interactionComplete(function () { wf._finish(); });
  }

  this.abort = function () {
    this.start();
    this.finish();
  }
}

function wfQuestion (args) {
  this.caption = args.caption;
  this.type = args.type;
  this.value = args.answer;
  this.choices = args.choices;
  this.required = args.required || false;
  this.validation = args.validation || function (ans) { return null; };
  this.domain = args.domain;
  this.domain_meta = args.meta;
  this.helptext = args.helptext;
  this.custom_layout = args.custom_layout;

  this.to_q = function () {
    return {'caption': this.caption,
            'datatype': this.type,
            'answer': this.value,
            'choices': this.choices,
            'required': this.required,
            'help': this.helptext,
            'domain': this.domain,
            'domain_meta': this.domain_meta,
            'customlayout': this.custom_layout};
  }

  this.validate = function () {
    if (this.required && this.value == null) {
      return "An answer is required";
    } else if (this.value != null) {
      return this.validation(this.value);
    }
  }
}

function wfQuery (query) {
  this.query = query;
  this.value = null;
  this.eval = function () {
    this.value = this.query();
  }
}

function wfAsyncQuery (query) {
  this.query = query;
  this.value = null;

  this.eval = function (callback) {
    queryObj = this;
    serverRequest(
      function (cb) {
        queryObj.query(function (val) {
            queryObj.value = val;
            cb();
          });
      },
      callback
    );
  }
}

function wfAlert (message) {
  this.message = message;

  this.to_q = function () {
    return {'caption': this.message,
            'datatype': 'info'};
  }
}

function workflowAdapter (workflow) {
  this.wf = workflow;

  this.wf_inst = null;
  this.history = null;
  this.active_question = null;

  this.loadForm = function () {
    this.wf_inst = this.wf.start();
    this.history = [];
    this.active_question = null;

    this._jumpNext();
  }

  this.answerQuestion = function (answer) {
    this.active_question.value = answer;

    var val_error = null;
    if (this.active_question instanceof wfQuestion) {
      val_error = this.active_question.validate();
    }

    if (val_error == null) {
      this._push_hist(answer, this.active_question);
    } else {
      showError(val_error);
    }
  }

  this.prevQuestion = function () {
    hist_length = this.history.length;
    while (hist_length > 0 && !this.history[hist_length - 1][0]) {
      hist_length--;
    }

    if (hist_length == 0) {
      this.wf.abort();
      return;
    }

    this.wf_inst = this.wf.start();
    for (var i = 0; i < hist_length; i++) {
      ev = this._getNext();
      ev.value = this.history[i][1];
      if (i == hist_length - 1) {
        this._activateQuestion(ev, false);
      }
    }

    while (this.history.length > hist_length - 1)
      this.history.pop();
  }

  this._getNext = function () {
    try {
      return this.wf_inst.next();
    } catch (e) {
      if (e instanceof StopIteration) {
        return null;
      } else {
        throw e;
      }
    }
  }

  this._jumpNext = function () {
    ev = this._getNext();
    if (ev == null) {
      this._formComplete();
    } else if (ev instanceof wfQuestion) {
      this._activateQuestion(ev, true);
    } else if (ev instanceof wfQuery) {
      ev.eval();
      this._push_hist(ev.value, ev);
    } else if (ev instanceof wfAsyncQuery) {
      var self = this;
      ev.eval(function () { self._push_hist(ev.value, ev); });
    } else if (ev instanceof wfAlert) {
      this._activateQuestion(ev, true);
    }
  }

  this._activateQuestion = function (ev, dir) {
    this.active_question = ev;
    renderQuestion(ev.to_q(), dir);
  }

  this._push_hist = function (answer, ev) {
    this.history.push([ev instanceof wfQuestion, answer]);
    this._jumpNext();
  }

  this._formComplete = function () {
    this.wf.finish();
  }

  this.abort = function () {
    this.wf.abort();
  }

  this.quitWarning = function () {
    if (this.wf.quitWarning) {
      return this.wf.quitWarning();
    } else {
      return {
        'main': 'You aren\'t finished yet. If you go HOME, you will throw out the answers you have entered so far.',
        'quit': 'Go HOME',
        'cancel': 'Stay and finish'
      }
    }
  }

}

function getQuestionAnswer () {
  return activeControl.getAnswer();
}

function answerQuestion () {
  gFormAdapter.answerQuestion(getQuestionAnswer());
}

function prevQuestion () {
  gFormAdapter.prevQuestion();
}

var interactionDone = false;
function interactionComplete (submit) {
  if (interactionDone) {
    //console.log('interaction already done; ignoring');
    return;
  }
  
  interactionDone = true;
  disableInput();
  var waitingTimer = setTimeout(function () { touchscreenUI.showWaiting(true); }, 300);
  
  submit();
}

function submit_redirect(params, path, method) {
  // hat tip: http://stackoverflow.com/questions/133925/javascript-post-request-like-a-form-submit
  method = method || "post"; // Set method to post by default, if not specified.
  path = path || "";
  // The rest of this code assumes you are not using a library.
  // It can be made less wordy if you use one.
  var form = document.createElement("form");
  form.setAttribute("method", method);
  form.setAttribute("action", path);
  
  for(var key in params) {
    var hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", key);
    hiddenField.setAttribute("value", params[key]);
    
    form.appendChild(hiddenField);
  }
  // required for FF 3+ compatibility
  document.body.appendChild(form);
  form.submit();
}