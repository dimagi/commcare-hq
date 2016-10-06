/*global CodeMirror */

// IE compliance
if (!Array.prototype.indexOf) {
    Array.prototype.indexOf = function (e) {
        var ix = -1;
        for (var i = 0; i < this.length; i++) {
            if (this[i] === e) {
                ix = i;
                break;
            }
        }
        return ix;
    };
}

function TaskQueue() {
    this.queue = [];
}

/*
 * Executes the queue in a FIFO action. If name is supplied, will execute the first
 * task for that name.
 */
TaskQueue.prototype.execute = function(name) {
    var task,
        idx;
    if (name) {
        idx = _.indexOf(_.pluck(this.queue, 'name'), name);
        if (idx === -1) { return; }
        task = this.queue.splice(idx, 1)[0];
    } else {
        task = this.queue.shift();
    }
    if (!task) { return; }
    task.fn.apply(task.thisArg, task.parameters);
};

TaskQueue.prototype.addTask = function (name, fn, parameters, thisArg) {
    var task = { name: name, fn: fn, parameters: parameters, thisArg: thisArg };
    this.queue.push(task);
    return task;
};

TaskQueue.prototype.clearTasks = function(name) {
    var idx;
    if (name) {
        idx = _.indexOf(_.pluck(this.queue, 'name'), name);
        while (idx !== -1) {
            this.queue.splice(idx, 1);
            idx = _.indexOf(_.pluck(this.queue, 'name'), name);
        }
    } else {
        this.queue = [];
    }
};

function WebFormSession(params) {

    var self = this;
    self.taskQueue = new TaskQueue();
    self.formContext = params.formContext;
    self.domain = params.domain;
    self.username = params.username;
    self.formplayerEnabled = params.formplayerEnabled;
    self.debuggerEnabled = params.debuggerEnabled;
    self.post_url = params.post_url;
    self.displayOptions = params.displayOptions;

    if (params.form_uid) {
        self.formSpec = {type: 'form-name', val: params.form_uid};
    } else if (params.form_content) {
        self.formSpec = {type: 'form-content', val: params.form_content};
    } else if (params.form_url) {
        self.formSpec = {type: 'form-url', val: params.form_url};
    }

    self.applyListeners();

    self.resourceMap = params.resourceMap;
    self.session_id = params.session_id || null;
    self.instance_xml = params.instance_xml;
    self.session_data = params.session_data || {};
    self.answerCallback = params.answerCallback;
    if (!self.session_data.host) {
        self.session_data.host = window.location.protocol + '//' + window.location.host;
    }

    self.onsubmit = params.onsubmit;
    self.uses_sql_backend = params.uses_sql_backend || false;

    // onload/onlanginfo
    self.onload = params.onload;
    self.onLoading = params.onLoading;
    self.onLoadingComplete = params.onLoadingComplete;

    self.onerror = params.onerror;

    self.urls = {
        xform: params.xform_url,
    };


    self.blockingRequestInProgress = false;
    self.lastRequestHandled = -1;
    self.numPendingRequests = 0;

    // workaround for "forever loading" bugs...
    $(document).ajaxStop(function () {
        self.NUM_PENDING_REQUESTS = 0;
        self.blockingRequestInProgress = false;
    });
}

WebFormSession.prototype.load = function($form, initLang) {
    if (this.session_id) {
        this.resumeForm($form, this.session_id);
    } else {
        this.loadForm($form, initLang);
    }
};

/**
 * Sends a request to the touchforms server
 * @param {Object} requestParams - request parameters to be sent
 * @param {function} callback - function to be called on success
 * @param {boolean} blocking - whether the request should be blocking
 */
WebFormSession.prototype.serverRequest = function (requestParams, callback, blocking) {
    var self = this;
    var url = self.urls.xform;
    if (requestParams.action === Formplayer.Const.SUBMIT && self.NUM_PENDING_REQUESTS) {
        self.taskQueue.addTask(requestParams.action, self.serverRequest, arguments, self);
    }

    requestParams.form_context = self.formContext;
    requestParams.domain = self.domain;
    requestParams.username = self.username;
    requestParams['session-id'] = self.session_id;
    // stupid hack for now to make up for both being used in different requests
    requestParams['session_id'] = self.session_id;
    requestParams['debuggerEnabled'] = self.debuggerEnabled;
    if (this.blockingRequestInProgress) {
        return;
    }
    this.blockingRequestInProgress = blocking;
    $.publish('session.block', blocking);

    this.numPendingRequests++;
    this.onLoading();

    if (self.formplayerEnabled){
        $.ajax({
            type: 'POST',
            url: url + "/" + requestParams.action,
            data: JSON.stringify(requestParams),
            contentType: "application/json",
            dataType: "json",
            crossDomain: {crossDomain: true},
            xhrFields: {withCredentials: true},
            success: function(resp) {
                self.handleSuccess(resp, callback);
            },
            error: function(resp, textStatus) {
                self.handleFailure(resp, textStatus);
            },
        });
    } else {
        $.ajax({
            type: 'POST',
            url: url,
            data: JSON.stringify(requestParams),
            dataType: "text",  // we don't use JSON because of a weird bug: http://manage.dimagi.com/default.asp?190983
            success: function(resp) {
                self.handleSuccess(JSON.parse(resp), callback);
            },
            error: function(resp, textStatus) {
                self.handleFailure(JSON.parse(resp), textStatus);
            },
        });
    }
};

WebFormSession.prototype.displayInstanceXml = function(resp) {
    var $instanceTab = $('#debugger-xml-instance-tab'),
        self = this,
        codeMirror;

    if (!self.debuggerEnabled || !resp.instanceXml || !resp.instanceXml.output) {
        return;
    }

    codeMirror = CodeMirror(function(el) {
        $('#xml-viewer-pretty').html(el);
    }, {
        value: resp.instanceXml.output,
        mode: 'xml',
        viewportMargin: Infinity,
        readOnly: true,
        lineNumbers: true,
    });

    $instanceTab.off();
    $instanceTab.on('shown.bs.tab', function() {
        codeMirror.refresh();
    });
};

/*
 * Handles a successful request to touchforms.
 * @param {Object} response - touchforms response object
 * @param {function} callback - callback to be called if no errors occured
 */
WebFormSession.prototype.handleSuccess = function(resp, callback) {
    var self = this;
    if (resp.status === 'error' || resp.error) {
        self.onerror(resp);
    } else {
        // ignore responses older than the most-recently handled
        if (resp.seq_id && resp.seq_id < self.lastRequestHandled) {
            return;
        }
        self.lastRequestHandled = resp.seq_id;

        try {
            callback(resp);
            self.displayInstanceXml(resp);
        } catch (err) {
            console.error(err);
            self.onerror({message: Formplayer.Utils.touchformsError(err)});
        }
    }

    $.publish('session.block', false);
    this.blockingRequestInProgress = false;

    self.numPendingRequests--;
    if (self.numPendingRequests === 0) {
        self.onLoadingComplete();
        self.taskQueue.execute(Formplayer.Const.SUBMIT);
        // Remove any submission tasks that have been queued up from spamming the submit button
        self.taskQueue.clearTasks(Formplayer.Const.SUBMIT);
    }
};

WebFormSession.prototype.handleFailure = function(resp, textStatus) {
    var errorMessage;
    if (textStatus === 'timeout') {
        errorMessage = Formplayer.Errors.TIMEOUT_ERROR;
    } else if (resp.hasOwnProperty('responseJSON')) {
        errorMessage = Formplayer.Utils.touchformsError(resp.responseJSON.message);
    }
    this.onerror({
        human_readable_message: errorMessage
    });
    this.onLoadingComplete();
};

/*
 * Subscribes to form action events which then get directed to a response to touchforms
 */
WebFormSession.prototype.applyListeners = function() {
    var self = this;
    $.unsubscribe([
        'formplayer.' + Formplayer.Const.ANSWER,
        'formplayer.' + Formplayer.Const.DELETE_REPEAT,
        'formplayer.' + Formplayer.Const.NEW_REPEAT,
        'formplayer.' + Formplayer.Const.EVALUATE_XPATH,
        'formplayer.' + Formplayer.Const.SUBMIT,
    ].join(' '));
    $.subscribe('formplayer.' + Formplayer.Const.SUBMIT, function(e, form) {
        self.submitForm(form);
    });
    $.subscribe('formplayer.' + Formplayer.Const.ANSWER, function(e, question) {
        self.answerQuestion(question);
    });
    $.subscribe('formplayer.' + Formplayer.Const.DELETE_REPEAT, function(e, group) {
        self.deleteRepeat(group);
    });
    $.subscribe('formplayer.' + Formplayer.Const.NEW_REPEAT, function(e, repeat) {
        self.newRepeat(repeat);
    });
    $.subscribe('formplayer.' + Formplayer.Const.EVALUATE_XPATH, function(e, xpath, callback) {
        self.evaluateXPath(xpath, callback);
    });
};

WebFormSession.prototype.loadForm = function($form, initLang) {
    var args = {
        'action': Formplayer.Const.NEW_FORM,
        'instance-content': this.instance_xml,
        'lang': initLang,
        'session-data': this.session_data,
        'domain': this.session_data.domain,
        'nav': 'fao',
        'uses_sql_backend': this.uses_sql_backend,
        'post_url': this.post_url,
        'oneQuestionPerScreen': true
    };

    args[this.formSpec.type] = this.formSpec.val;

    // handle preloaders (deprecated) for backwards compatibilty
    if (args['session-data'] && args['session-data'].preloaders) {
        if (args['session-data'] === null) {
            args['session-data'] = {};
        }
        args['session-data'].preloaders = init_preloaders(args['session-data'].preloaders);
    }

    this.initForm(args, $form);
};

WebFormSession.prototype.resumeForm = function($form, session_id) {
    var args = {
        "action": Formplayer.Const.CURRENT
    };

    this.initForm(args, $form);
};

WebFormSession.prototype.answerQuestion = function(q) {
    var self = this;
    var ix = getIx(q);
    var answer = q.answer();

    this.serverRequest({
            'action': Formplayer.Const.ANSWER,
            'ix': ix,
            'answer': answer
        },
        function(resp) {
            $.publish('session.reconcile', [resp, q]);
            if (self.answerCallback !== undefined) {
                self.answerCallback(self.session_id);
            }
        });
};

WebFormSession.prototype.evaluateXPath = function(xpath, callback) {
    this.serverRequest({
            'action': Formplayer.Const.EVALUATE_XPATH,
            'xpath': xpath
        },
        function(resp) {
            callback(resp.output, resp.status);
        });
};

WebFormSession.prototype.newRepeat = function(repeat) {
    this.serverRequest({
            'action': Formplayer.Const.NEW_REPEAT,
            'ix': getIx(repeat)
        },
        function(resp) {
            $.publish('session.reconcile', [resp, repeat]);
        },
        true);
};

WebFormSession.prototype.deleteRepeat = function(repetition) {
    var juncture = getIx(repetition.parent);
    var rep_ix = +(repetition.rel_ix().replace('_',':').split(":").slice(-1)[0]);
    this.serverRequest({
            'action': Formplayer.Const.DELETE_REPEAT,
            'ix': rep_ix,
            'form_ix': juncture
        },
        function(resp) {
            $.publish('session.reconcile', [resp, repetition]);
        },
        true);
};

WebFormSession.prototype.switchLanguage = function(lang) {
    this.serverRequest({
            'action': Formplayer.Const.SET_LANG,
            'lang': lang
        },
        function(resp) {
            $.publish('session.reconcile', [resp, lang]);
        });
};

WebFormSession.prototype.submitForm = function(form) {
    var self = this,
        answers = {},
        accumulate_answers,
        prevalidated = true;

    accumulate_answers = function(o) {
        if (ko.utils.unwrapObservable(o.type) !== 'question') {
            if(o.hasOwnProperty("children")) {
                $.each(o.children(), function (i, val) {
                    accumulate_answers(val);
                });
            }
        } else {
            if (o.isValid()) {
                if(ko.utils.unwrapObservable(o.datatype) !== "info") {
                    answers[getIx(o)] = ko.utils.unwrapObservable(o.answer);
                }
            } else {
                prevalidated = false;
            }
        }
    };
    accumulate_answers(form);
    this.serverRequest({
            'action': Formplayer.Const.SUBMIT,
            'answers': answers,
            'prevalidated': prevalidated
        },
        function(resp) {
            if (resp.status == 'success') {
                form.submitting();
                self.onsubmit(resp);
            } else {
                $.each(resp.errors, function(ix, error) {
                    self.serverError(getForIx(form, ix), error);
                });
                alert('There are errors in this form; they must be corrected before the form can be submitted.');
            }
        },
        true);
};

WebFormSession.prototype.serverError = function(q, resp) {
    if (resp.type === "required") {
        q.serverError("An answer is required");
    } else if (resp.type === "constraint") {
        q.serverError(resp.reason || 'This answer is outside the allowed range.');
    }
};

WebFormSession.prototype.initForm = function(args, $form) {
    var self = this;
    this.serverRequest(args, function(resp) {
        self.renderFormXml(resp, $form, self.displayOptions);
        self.onload(self, resp);
    });
};

WebFormSession.prototype.renderFormXml = function (resp, $form) {
    var self = this;
    self.session_id = self.session_id || resp.session_id;
    self.form = Formplayer.Utils.initialRender(resp, self.resourceMap, $form);
    self.displayInstanceXml(resp);
};
