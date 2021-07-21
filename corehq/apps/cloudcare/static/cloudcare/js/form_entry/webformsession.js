hqDefine("cloudcare/js/form_entry/webformsession", function () {
    var Const = hqImport("cloudcare/js/form_entry/const"),
        Utils = hqImport("cloudcare/js/form_entry/utils"),
        UI = hqImport("cloudcare/js/form_entry/fullform-ui");

    function WebFormSession(params) {
        var self = {};

        self.taskQueue = hqImport("cloudcare/js/form_entry/task_queue").TaskQueue();
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

        self.blockingStatus = Const.BLOCK_NONE;
        self.lastRequestHandled = -1;

        // workaround for "forever loading" bugs...
        $(document).ajaxStop(function () {
            self.blockingStaus = Const.BLOCK_NONE;
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
         * @param {boolean} blocking - one of Const.BLOCK_*, defaults to BLOCK_NONE
         * @param {function} failureCallback - function to be called on failure
         * @param {function} errorResponseCallback - function to be called on a "success" response with .status = 'error'
         *      this function should return true to also run default behavior afterwards, or false to prevent it
         */
        self.serverRequest = function (requestParams, successCallback, blocking, failureCallback, errorResponseCallback) {
            if (self.blockingStatus === Const.BLOCK_ALL) {
                return;
            }
            self.blockingStatus = blocking || Const.BLOCK_NONE;
            $.publish('session.block', blocking);
            self.onLoading();

            if (requestParams.action === Const.SUBMIT) {
                // Remove any submission tasks that have been queued up from spamming the submit button
                self.taskQueue.clearTasks(Const.SUBMIT);
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

            return $.ajax({
                type: 'POST',
                url: self.urls.xform + "/" + requestParams.action,
                data: JSON.stringify(requestParams),
                contentType: "application/json",
                dataType: "json",
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
            });
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
                        message: Utils.touchformsError(err),
                    });
                }
            }

            self.blockingStatus = Const.BLOCK_NONE;
            $.publish('session.block', self.blockingStatus);
        };

        self.handleFailure = function (resp, action, textStatus, failureCallback) {
            var self = this,
                errorMessage = null,
                isHTML = false,
                Errors = hqImport("cloudcare/js/form_entry/errors");
            if (resp.status === 423) {
                errorMessage = Errors.LOCK_TIMEOUT_ERROR;
            } else if (resp.status === 401) {
                errorMessage = Utils.reloginErrorHtml();
                isHTML = true;
            } else if (textStatus === 'timeout') {
                errorMessage = Errors.TIMEOUT_ERROR;
            } else if (!window.navigator.onLine) {
                errorMessage = Errors.NO_INTERNET_ERROR;
                if (action === Const.SUBMIT) {
                    $('.submit').prop('disabled', false);
                    $('.form-control').prop('disabled', false);
                }
            } else if (_.has(resp, 'responseJSON') && resp.responseJSON !== undefined) {
                errorMessage = Utils.touchformsError(resp.responseJSON.message);
            }

            hqImport('cloudcare/js/util').reportFormplayerErrorToHQ({
                type: 'webformsession_request_failure',
                request: action,
                readableErrorMessage: errorMessage,
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
            });
            this.onLoadingComplete();
        };

        /*
         * Subscribes to form action events which then get directed to a response to touchforms
         */
        self.applyListeners = function () {
            var self = this;
            $.unsubscribe([
                'formplayer.' + Const.ANSWER,
                'formplayer.' + Const.DELETE_REPEAT,
                'formplayer.' + Const.NEW_REPEAT,
                'formplayer.' + Const.EVALUATE_XPATH,
                'formplayer.' + Const.SUBMIT,
                'formplayer.' + Const.NEXT_QUESTION,
                'formplayer.' + Const.PREV_QUESTION,
                'formplayer.' + Const.QUESTIONS_FOR_INDEX,
                'formplayer.' + Const.FORMATTED_QUESTIONS,
                'formplayer.' + Const.CHANGE_LANG,
            ].join(' '));
            $.subscribe('formplayer.' + Const.SUBMIT, function (e, form) {
                self.submitForm(form);
            });
            $.subscribe('formplayer.' + Const.ANSWER, function (e, question) {
                self.answerQuestion(question);
            });
            $.subscribe('formplayer.' + Const.DELETE_REPEAT, function (e, group) {
                self.deleteRepeat(group);
            });
            $.subscribe('formplayer.' + Const.NEW_REPEAT, function (e, repeat) {
                self.newRepeat(repeat);
            });
            $.subscribe('formplayer.' + Const.EVALUATE_XPATH, function (e, xpath, callback) {
                self.evaluateXPath(xpath, callback);
            });
            $.subscribe('formplayer.' + Const.NEXT_QUESTION, function (e, opts) {
                self.nextQuestion(opts);
            });
            $.subscribe('formplayer.' + Const.PREV_QUESTION, function (e, opts) {
                self.prevQuestion(opts);
            });
            $.subscribe('formplayer.' + Const.QUESTIONS_FOR_INDEX, function (e, index) {
                self.getQuestionsForIndex(index);
            });
            $.subscribe('formplayer.' + Const.FORMATTED_QUESTIONS, function (e, callback) {
                self.getFormattedQuestions(callback);
            });
            $.subscribe('formplayer.' + Const.CHANGE_LANG, function (e, lang) {
                self.changeLang(lang);
            });
        };

        self.loadForm = function ($form, initLang) {
            var args = {
                'action': Const.NEW_FORM,
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
                "action": Const.CURRENT,
            };

            this.initForm(args, $form);
        };

        self.answerQuestion = function (q) {
            var self = this;
            var ix = UI.getIx(q);
            var answer = q.answer();
            var oneQuestionPerScreen = self.isOneQuestionPerScreen();
            var form = q.form();
            var erroredLabels = form.erroredLabels();

            this.serverRequest(
                {
                    'action': Const.ANSWER,
                    'ix': ix,
                    'answer': answer,
                    'answersToValidate': erroredLabels,
                    'oneQuestionPerScreen': oneQuestionPerScreen,
                },
                function (resp) {
                    $.publish('session.reconcile', [resp, q]);
                    if (self.answerCallback !== undefined) {
                        self.answerCallback(self.session_id);
                    }
                    $.each(erroredLabels, function (ix, label) {
                        self.serverError(UI.getForIx(form, ix), resp.errors.ix ? resp.errors.ix : null);
                    });
                },
                Const.BLOCK_SUBMIT,
                function () {
                    q.serverError(
                        gettext("We were unable to save this answer. Please try again later."));
                    q.pendingAnswer(Const.NO_PENDING_ANSWER);
                });
        };

        self.nextQuestion = function (opts) {
            this.serverRequest(
                {
                    'action': Const.NEXT_QUESTION,
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
                    'action': Const.PREV_QUESTION,
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
                    'action': Const.QUESTIONS_FOR_INDEX,
                    'ix': index,
                },
                function (resp) {
                    $.publish('session.reconcile', [resp, {}]);
                });
        };

        self.evaluateXPath = function (xpath, callback) {
            this.serverRequest(
                {
                    'action': Const.EVALUATE_XPATH,
                    'xpath': xpath,
                },
                function (resp) {
                    callback(resp);
                });
        };

        self.getFormattedQuestions = function (callback) {
            this.serverRequest(
                {
                    'action': Const.FORMATTED_QUESTIONS,
                },
                function (resp) {
                    callback(resp);
                });
        };

        self.newRepeat = function (repeat) {
            this.serverRequest(
                {
                    'action': Const.NEW_REPEAT,
                    'ix': UI.getIx(repeat),
                },
                function (resp) {
                    $.publish('session.reconcile', [resp, repeat]);
                },
                Const.BLOCK_ALL);
        };

        self.deleteRepeat = function (repetition) {
            var juncture = UI.getIx(repetition.parent);
            var repIx = +(repetition.rel_ix().replace(/_/g, ':').split(":").slice(-1)[0]);
            this.serverRequest(
                {
                    'action': Const.DELETE_REPEAT,
                    'ix': repIx,
                    'form_ix': juncture,
                },
                function (resp) {
                    $.publish('session.reconcile', [resp, repetition]);
                },
                Const.BLOCK_ALL);
        };

        self.changeLang = function (lang) {
            this.serverRequest(
                {
                    'action': Const.CHANGE_LOCALE,
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
                                _answers[UI.getIx(o)] = ko.utils.unwrapObservable(o.answer);
                            } else {
                                _answers[UI.getIx(o)] = "ok";
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
                            'action': Const.SUBMIT,
                            'answers': answers,
                            'prevalidated': prevalidated,
                        };
                    };
                    requestCallback.action = Const.SUBMIT;
                    self.serverRequest(
                        requestCallback,
                        function (resp) {
                            form.isSubmitting(false);
                            if (resp.status === 'success') {
                                self.onsubmit(resp);
                            } else {
                                $.each(resp.errors, function (ix, error) {
                                    self.serverError(UI.getForIx(form, ix), error);
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
                        Const.BLOCK_ALL,
                        undefined,
                        function () {
                            form.isSubmitting(false);
                            return true;
                        }
                    );
                }, 250);
        };

        self.serverError = function (q, resp) {
            if (!resp) {
                q.serverError(null);
            } else if (resp.type === "required") {
                q.serverError("An answer is required");
            } else if (resp.type === "constraint") {
                q.serverError(resp.reason || 'This answer is outside the allowed range.');
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
            self.form = Utils.initialRender(resp, self.resourceMap, $form);
            if (resp.shouldAutoSubmit) {
                self.submitForm(self.form);
            }
        };

        // Initialize
        self.applyListeners();

        return self;
    }

    return {
        WebFormSession: WebFormSession,
    };
});
