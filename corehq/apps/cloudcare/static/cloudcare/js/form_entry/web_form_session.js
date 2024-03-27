'use strict';
hqDefine("cloudcare/js/form_entry/web_form_session", function () {
    var cloudcareUtils = hqImport("cloudcare/js/utils"),
        constants = hqImport("cloudcare/js/form_entry/const"),
        errors = hqImport("cloudcare/js/form_entry/errors"),
        taskQueue = hqImport("cloudcare/js/form_entry/task_queue"),
        formEntryUtils = hqImport("cloudcare/js/form_entry/utils"),
        formUI = hqImport("cloudcare/js/form_entry/form_ui");

    function WebFormSession(params) {
        var self = {};

        self.taskQueue = taskQueue.TaskQueue();
        self.formContext = params.formContext;
        self.domain = params.domain;
        self.username = params.username;
        self.debuggerEnabled = params.debuggerEnabled;
        self.formplayerEnabled = params.formplayerEnabled;
        self.post_url = params.post_url;
        self.displayOptions = params.displayOptions;
        self.restoreAs = params.restoreAs;

        if (params.form_uid) {
            self.formSpec = {
                type: 'form-name',
                val: params.form_uid,
            };
        } else if (params.form_content) {
            self.formSpec = {
                type: 'form-content',
                val: params.form_content,
            };
        } else if (params.form_url) {
            self.formSpec = {
                type: 'form-url',
                val: params.form_url,
            };
        }

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

        self.blockingStatus = constants.BLOCK_NONE;
        self.lastRequestHandled = -1;

        // workaround for "forever loading" bugs...
        $(document).ajaxStop(function () {
            self.blockingStaus = constants.BLOCK_NONE;
        });

        self.load = function ($form, initLang) {
            if (this.session_id) {
                this.resumeForm($form);
            } else {
                this.loadForm($form, initLang);
            }
        };

        self.isOneQuestionPerScreen = function () {
            if (self.displayOptions === undefined) {
                return false;
            }
            return ko.utils.unwrapObservable(self.displayOptions.oneQuestionPerScreen);
        };
        /**
         * Sends a request to the touchforms server
         * @param {Object} requestParams - request parameters to be sent
         * @param {function} successCallback - function to be called on success
         * @param {boolean} blocking - one of constants.BLOCK_*, defaults to BLOCK_NONE
         * @param {function} failureCallback - function to be called on failure
         * @param {function} errorResponseCallback - function to be called on a "success" response with .status = 'error'
         *      this function should return true to also run default behavior afterwards, or false to prevent it
         */
        // eslint-disable-next-line no-unused-vars
        self.serverRequest = function (requestParams, successCallback, blocking, failureCallback, errorResponseCallback) {
            if (self.blockingStatus === constants.BLOCK_ALL) {
                return;
            }
            self.blockingStatus = blocking || constants.BLOCK_NONE;
            $.publish('session.block', blocking);
            self.onLoading();

            if (requestParams.action === constants.SUBMIT) {
                // Remove any submission tasks that have been queued up from spamming the submit button
                self.taskQueue.clearTasks(constants.SUBMIT);
            }

            self.taskQueue.addTask(requestParams.action, self._serverRequest, arguments, self);
        };

        self._serverRequest = function (requestParams, successCallback, blocking, failureCallback, errorResponseCallback) {
            var self = this;

            if (_.isFunction(requestParams)) {
                requestParams = requestParams();
            }

            requestParams.form_context = self.formContext;
            requestParams.domain = self.domain;
            requestParams.username = self.username;
            requestParams.restoreAs = self.restoreAs;
            requestParams['session-id'] = self.session_id;
            // stupid hack for now to make up for both being used in different requests
            requestParams['session_id'] = self.session_id;
            requestParams['debuggerEnabled'] = self.debuggerEnabled;
            requestParams['tz_offset_millis'] = (new Date()).getTimezoneOffset() * 60 * 1000 * -1;
            requestParams['tz_from_browser'] = Intl.DateTimeFormat().resolvedOptions().timeZone;

            var contentParams = {};
            if (requestParams.action === constants.ANSWER_MEDIA) {
                var newData = new FormData();
                newData.append("file", requestParams.file);

                // use a blob here so that we can set the content type
                let answerData = new Blob(
                    [JSON.stringify(_.omit(requestParams, "file"))],
                    {type: 'application/json'}
                );
                newData.append("answer", answerData);

                contentParams = {
                    contentType: false,
                    data: newData,
                };
            } else {
                contentParams = {
                    contentType: "application/json",
                    data: JSON.stringify(requestParams),
                };
            }
            return $.ajax(_.extend({
                type: 'POST',
                url: self.urls.xform + "/" + requestParams.action,
                processData: false,
                crossDomain: {
                    crossDomain: true,
                },
                xhrFields: {
                    withCredentials: true,
                },
                success: function (resp) {
                    self.handleSuccess(resp, requestParams.action, successCallback, errorResponseCallback);
                },
                error: function (resp, textStatus) {
                    self.handleFailure(resp, requestParams.action, textStatus, failureCallback);
                },
            }, contentParams));
        };

        /*
         * Handles a successful request to touchforms.
         * @param {Object} response - touchforms response object
         * @param {function} callback - callback to be called if no errors occured
         */
        self.handleSuccess = function (resp, action, successCallback, errorResponseCallback) {
            var self = this;
            errorResponseCallback = errorResponseCallback || function () { return true; };
            if (resp.status === 'error' || resp.error) {
                if (errorResponseCallback()) {
                    self.onerror(resp);
                }
            } else {
                // ignore responses older than the most-recently handled
                if (resp.seq_id && resp.seq_id < self.lastRequestHandled) {
                    return;
                }
                self.lastRequestHandled = resp.seq_id;

                try {
                    successCallback(resp);
                } catch (err) {
                    console.error(err);
                    self.onerror({
                        human_readable_message: formEntryUtils.jsError(err),
                    });
                }
            }

            self.blockingStatus = constants.BLOCK_NONE;
            $.publish('session.block', self.blockingStatus);
        };

        self.handleFailure = function (resp, action, textStatus, failureCallback) {
            var self = this,
                errorMessage = null,
                isHTML = false;
            if (resp.status === 423) {
                errorMessage = errors.LOCK_TIMEOUT_ERROR;
            } else if (resp.status === 401) {
                errorMessage = errors.INACTIVITY_ERROR;
                isHTML = true;
            } else if (textStatus === 'timeout') {
                errorMessage = errors.TIMEOUT_ERROR;
            } else if (!window.navigator.onLine) {
                errorMessage = errors.NO_INTERNET_ERROR;
                if (action === constants.SUBMIT) {
                    $('.submit').prop('disabled', false);
                    $('.form-control').prop('disabled', false);
                }
            } else if (_.has(resp, 'responseJSON') && resp.responseJSON !== undefined) {
                errorMessage = formEntryUtils.touchformsError(resp.responseJSON.message);
            }

            cloudcareUtils.reportFormplayerErrorToHQ({
                type: 'webformsession_request_failure',
                request: action,
                message: errorMessage,
                statusText: resp.statusText,
                state: resp.state ? resp.state() : null,
                status: resp.status,
                domain: self.domain,
                username: self.username,
                restoreAs: self.restoreAs,
            });

            if (failureCallback) {
                failureCallback();
            }
            this.onerror({
                human_readable_message: errorMessage,
                is_html: isHTML,
                reportToHq: false,
            });
            this.onLoadingComplete();
        };

        /*
         * Subscribes to form action events which then get directed to a response to touchforms
         */
        self.applyListeners = function () {
            var self = this;
            $.unsubscribe([
                'formplayer.' + constants.ANSWER,
                'formplayer.' + constants.CLEAR_ANSWER,
                'formplayer.' + constants.DELETE_REPEAT,
                'formplayer.' + constants.NEW_REPEAT,
                'formplayer.' + constants.EVALUATE_XPATH,
                'formplayer.' + constants.SUBMIT,
                'formplayer.' + constants.NEXT_QUESTION,
                'formplayer.' + constants.PREV_QUESTION,
                'formplayer.' + constants.QUESTIONS_FOR_INDEX,
                'formplayer.' + constants.FORMATTED_QUESTIONS,
                'formplayer.' + constants.CHANGE_LANG,
            ].join(' '));
            $.subscribe('formplayer.' + constants.SUBMIT, function (e, form) {
                self.submitForm(form);
            });
            $.subscribe('formplayer.' + constants.ANSWER, function (e, question) {
                self.answerQuestion(question);
            });
            $.subscribe('formplayer.' + constants.CLEAR_ANSWER, function (e, question) {
                self.answerQuestion(question);
            });
            $.subscribe('formplayer.' + constants.DELETE_REPEAT, function (e, group) {
                self.deleteRepeat(group);
            });
            $.subscribe('formplayer.' + constants.NEW_REPEAT, function (e, repeat) {
                self.newRepeat(repeat);
            });
            $.subscribe('formplayer.' + constants.EVALUATE_XPATH, function (e, xpath, callback) {
                self.evaluateXPath(xpath, callback);
            });
            $.subscribe('formplayer.' + constants.NEXT_QUESTION, function (e, opts) {
                self.nextQuestion(opts);
            });
            $.subscribe('formplayer.' + constants.PREV_QUESTION, function (e, opts) {
                self.prevQuestion(opts);
            });
            $.subscribe('formplayer.' + constants.QUESTIONS_FOR_INDEX, function (e, index) {
                self.getQuestionsForIndex(index);
            });
            $.subscribe('formplayer.' + constants.FORMATTED_QUESTIONS, function (e, callback) {
                self.getFormattedQuestions(callback);
            });
            $.subscribe('formplayer.' + constants.CHANGE_LANG, function (e, lang) {
                self.changeLang(lang);
            });
        };

        self.loadForm = function ($form, initLang) {
            var args = {
                'action': constants.NEW_FORM,
                'instance-content': this.instance_xml,
                'lang': initLang,
                'session-data': this.session_data,
                'domain': this.session_data.domain,
                'nav': 'fao',
                'uses_sql_backend': this.uses_sql_backend,
                'post_url': this.post_url,
                'oneQuestionPerScreen': this.isOneQuestionPerScreen(),
            };

            args[this.formSpec.type] = this.formSpec.val;

            this.initForm(args, $form);
        };

        self.resumeForm = function ($form) {
            var args = {
                "action": constants.CURRENT,
            };

            this.initForm(args, $form);
        };

        self.answerQuestion = function (q) {
            var self = this;
            var ix = formUI.getIx(q);
            var answer = q.entry.xformAction === constants.CLEAR_ANSWER ? constants.NO_ANSWER : q.answer();
            var oneQuestionPerScreen = self.isOneQuestionPerScreen();
            var form = q.form();

            // We revalidate any errored labels while answering any of the questions
            var erroredLabels = form.erroredLabels();
            sessionStorage.answerQuestionInProgress = true;
            this.serverRequest(
                _.extend({
                    'action': q.entry.xformAction,
                    'ix': ix,
                    'answer': answer,
                    'answersToValidate': erroredLabels,
                    'oneQuestionPerScreen': oneQuestionPerScreen,
                }, q.entry.xformParams()),
                function (resp) {
                    sessionStorage.answerQuestionInProgress = false;
                    self.updateXformAction(q);
                    if (q.formplayerMediaRequest) {
                        q.formplayerMediaRequest.resolve();
                    }
                    $.publish('session.reconcile', [resp, q]);
                    if (self.answerCallback !== undefined) {
                        self.answerCallback(self.session_id);
                    }
                    $.each(erroredLabels, function (ix) {
                        self.serverError(formUI.getForIx(form, ix), resp.errors[ix]);
                    });
                },
                constants.BLOCK_SUBMIT,
                function () {
                    self.updateXformAction(q);
                    if (q.formplayerMediaRequest) {
                        q.formplayerMediaRequest.reject();
                    }
                    q.serverError(
                        gettext("We were unable to save this answer. Please try again later."));
                    q.pendingAnswer(constants.NO_PENDING_ANSWER);
                });
        };

        self.updateXformAction = function (q) {
            if (q.entry.xformAction === constants.CLEAR_ANSWER) {
                q.entry.xformAction = (q.entry.templateType === "file" || q.entry.templateType === "signature")
                    ? constants.ANSWER_MEDIA : constants.ANSWER;
            }
        };

        self.nextQuestion = function (opts) {
            this.serverRequest(
                {
                    'action': constants.NEXT_QUESTION,
                },
                function (resp) {
                    opts.callback(parseInt(resp.currentIndex), resp.isAtFirstIndex, resp.isAtLastIndex);
                    resp.title = opts.title;
                    $.publish('session.reconcile', [resp, {}]);
                });
        };

        self.prevQuestion = function (opts) {
            this.serverRequest(
                {
                    'action': constants.PREV_QUESTION,
                },
                function (resp) {
                    opts.callback(parseInt(resp.currentIndex), resp.isAtFirstIndex, resp.isAtLastIndex);
                    resp.title = opts.title;
                    $.publish('session.reconcile', [resp, {}]);
                });
        };

        self.getQuestionsForIndex = function (index) {
            this.serverRequest(
                {
                    'action': constants.QUESTIONS_FOR_INDEX,
                    'ix': index,
                },
                function (resp) {
                    $.publish('session.reconcile', [resp, {}]);
                });
        };

        self.evaluateXPath = function (xpath, callback) {
            this.serverRequest(
                {
                    'action': constants.EVALUATE_XPATH,
                    'xpath': xpath,
                },
                function (resp) {
                    callback(resp);
                });
        };

        self.getFormattedQuestions = function (callback) {
            this.serverRequest(
                {
                    'action': constants.FORMATTED_QUESTIONS,
                },
                function (resp) {
                    callback(resp);
                });
        };

        self.newRepeat = function (repeat) {
            this.serverRequest(
                {
                    'action': constants.NEW_REPEAT,
                    'ix': formUI.getIx(repeat),
                },
                function (resp) {
                    $.publish('session.reconcile', [resp, repeat]);
                },
                constants.BLOCK_ALL);
        };

        self.deleteRepeat = function (repetition) {
            var juncture = formUI.getIx(repetition.parent.parent);
            var repIx = +(repetition.rel_ix().replace(/_/g, ':').split(":").slice(-1)[0]);
            this.serverRequest(
                {
                    'action': constants.DELETE_REPEAT,
                    'ix': repIx,
                    'form_ix': juncture,
                },
                function (resp) {
                    $.publish('session.reconcile', [resp, repetition]);
                },
                constants.BLOCK_ALL);
        };

        self.changeLang = function (lang) {
            this.serverRequest(
                {
                    'action': constants.CHANGE_LOCALE,
                    'locale': lang,
                },
                function (resp) {
                    $.publish('session.reconcile', [resp, lang]);
                });
        };

        self.submitForm = function (form) {
            var self = this,
                accumulateAnswers,
                prevalidated = true;

            accumulateAnswers = function (o) {
                var _answers = {},
                    _accumulateAnswers;

                _accumulateAnswers = function (o) {
                    if (ko.utils.unwrapObservable(o.type) !== 'question') {
                        if (_.has(o, "children")) {
                            $.each(o.children(), function (i, val) {
                                _accumulateAnswers(val);
                            });
                        }
                    } else {
                        if (o.isValid()) {
                            if (ko.utils.unwrapObservable(o.datatype) !== "info") {
                                _answers[formUI.getIx(o)] = ko.utils.unwrapObservable(o.answer);
                            } else {
                                _answers[formUI.getIx(o)] = "OK";
                            }
                        } else {
                            prevalidated = false;
                        }
                    }
                };
                _accumulateAnswers(o);
                return _answers;
            };

            form.isSubmitting(true);
            var submitAttempts = 0,
                timer = setInterval(function () {
                    if (form.blockSubmit() && submitAttempts < 10) {
                        submitAttempts++;
                        return;
                    }
                    clearInterval(timer);

                    var requestCallback = function () {
                        var answers = accumulateAnswers(form);
                        return {
                            'action': constants.SUBMIT,
                            'answers': answers,
                            'prevalidated': prevalidated,
                        };
                    };
                    requestCallback.action = constants.SUBMIT;
                    self.serverRequest(
                        requestCallback,
                        function (resp) {
                            form.isSubmitting(false);
                            if (resp.status === 'success') {
                                self.onsubmit(resp);
                            } else {
                                $.each(resp.errors, function (ix, error) {
                                    self.serverError(formUI.getForIx(form, ix), error);
                                });
                                if (resp.status === 'too-many-requests') {
                                    alert(gettext("We’re unable to submit this form right now due to high system usage. \n\n" +
                                        "Please keep this window open and try again in a minute, " +
                                        "or come back to this form in Incomplete Forms later."));
                                } else if (resp.notification) {
                                    alert(gettext("Form submission failed with error") + ": \n\n" +
                                        resp.notification.message + ". \n\n " +
                                        "This must be corrected before the form can be submitted.");
                                }
                            }
                        },
                        constants.BLOCK_ALL,
                        undefined,
                        function () {
                            form.isSubmitting(false);
                            return true;
                        }
                    );
                }, 250);
        };

        self.serverError = function (q, resp) {
            if (!q) {
                // q is no longer visible (display condition has hidden it)
                return;
            }
            if (!resp) {
                q.serverError(null);
            } else if (resp.type === "required") {
                q.serverError(gettext("An answer is required"));
            } else if (resp.type === "constraint") {
                q.serverError(resp.reason || gettext('This answer is outside the allowed range.'));
            }
        };

        self.initForm = function (args, $form) {
            var self = this;
            this.serverRequest(args, function (resp) {
                self.renderFormXml(resp, $form, self.displayOptions);
                self.onload(self, resp);
            });
        };

        self.renderFormXml = function (resp, $form) {
            var self = this;
            self.session_id = self.session_id || resp.session_id;
            var promise = formEntryUtils.initialRender(resp, self.resourceMap, $form);
            $.when(promise).done(function (form) {
                self.form = form;
                if (resp.shouldAutoSubmit) {
                    self.submitForm(self.form);
                }
            });
        };

        // Initialize
        self.applyListeners();

        return self;
    }

    return {
        WebFormSession: WebFormSession,
    };
});
