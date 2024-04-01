'use strict';
hqDefine('cloudcare/js/debugger/debugger', [
    'jquery',
    'knockout',
    'underscore',
    'clipboard/dist/clipboard',
    'ace-builds/src-min-noconflict/ace',
    'analytix/js/kissmetrix',
    'reports/js/readable_form',
    'hqwebapp/js/atwho',    // $.atwho
    'ace-builds/src-min-noconflict/mode-json',
    'ace-builds/src-min-noconflict/mode-xml',
    'ace-builds/src-min-noconflict/ext-searchbox',
], function (
    $,
    ko,
    _,
    Clipboard,
    ace,
    kissmetrics,
    readableForm
) {
    /**
     * These define tabs that are availabe in the debugger.
     * {
     *   id: <id of the tab HTML element>,
     *   tab: <link to corresponding tab content. sets the href attribute>
     *   tabTemplate: <id of the tab's template>
     *   label: <label of the tab being displayed>
     * }
     */
    var DebuggerTabs = {
        FORM_DATA: {
            id: 'debugger-form-data-tab',
            tab: 'debugger-form-data',
            tabTemplate: 'debugger-form-data-template',
            label: gettext('Form Data'),
        },
        FORM_XML: {
            id: 'debugger-xml-instance-tab',
            tab: 'debugger-xml-instance',
            tabTemplate: 'debugger-xml-instance-template',
            label: gettext('Form XML'),
        },
        EVAL_XPATH: {
            id: 'debugger-evaluate-xpath-tab',
            tab: 'debugger-evaluate',
            tabTemplate: 'debugger-evaluate-template',
            label: gettext('Evaluate XPath'),
        },
    };

    var TabIDs = {
        FORM_DATA: 'FORM_DATA',
        FORM_XML: 'FORM_XML',
        EVAL_XPATH: 'EVAL_XPATH',
    };

    var SessionTypes = {
        FORM: 'form',
        MENU: 'menu',
    };

    var CloudCareDebugger = function (options) {
        var self = this;
        self.options = options || {};
        _.defaults(self.options, {
            baseUrl: null,
            formSessionId: null,
            selections: null,
            username: null,
            restoreAs: null,
            domain: null,
            appId: null,
            tabs: [
                TabIDs.FORM_DATA,
                TabIDs.FORM_XML,
                TabIDs.EVAL_XPATH,
            ],
        });

        self.registeredTabIds = self.options.tabs;
        self.tabs = DebuggerTabs;

        self.evalXPath = new EvaluateXPath(options);
        self.isMinimized = ko.observable(true);

        self.expandAriaLabel = gettext('Expand Data Preview');
        self.collapseAriaLabel = gettext('Collapse Data Preview');

        // Whether or not the debugger is in the middle of updating from an ajax request
        self.updating = ko.observable(false);

        self.toggleState = function () {
            self.isMinimized(!self.isMinimized());
            // Wait to set the content heigh until after the CSS animation has completed.
            // In order to support multiple heights, we set the height with javascript since
            // a div inside a fixed position element cannot scroll unless a height is explicitly set.
            setTimeout(self.setContentHeight, 1001);

            if (!self.isMinimized()) {
                self.updating(true);
                self.onUpdate();
            }
            kissmetrics.track.event('[app-preview] User toggled CloudCare debugger');
        };


        self.collapseNavbar = function () {
            $('.navbar-collapse').collapse('hide');
        };

        self.setContentHeight = function () {
            var contentHeight;
            if (self.isMinimized()) {
                $('.debugger-content').outerHeight(0);
            } else {
                contentHeight = ($('.debugger').outerHeight() -
                    $('.debugger-tab-title').outerHeight() -
                    $('.debugger-navbar').outerHeight());
                $('.debugger-content').outerHeight(contentHeight);
            }
        };

        // Called afterRender, ensures that the debugger takes the whole screen
        self.adjustWidth = function () {
            var $debug = $('#instance-xml-home'),
                $body = $('body');

            $debug.width($body.width());
        };
    };

    // By default do nothing when updating the debugger
    CloudCareDebugger.prototype.onUpdate = function () {
        this.updating(false);
    };

    var CloudCareDebuggerFormEntry = function (options) {
        var self = this;
        CloudCareDebugger.call(self, $.extend({ sessionType: SessionTypes.FORM }, options));

        self.formattedQuestionsHtml = ko.observable('');
        self.instanceXml = ko.observable('');
        self.instanceXml.subscribe(function (newXml) {
            var $viewer = $('#xml-viewer-pretty'),
                editor = ace.edit($viewer.get(0), {
                    showPrintMargin: false,
                    maxLines: 40,
                    minLines: 3,
                    fontSize: 14,
                    wrap: true,
                    useWorker: false,
                });
            editor.setReadOnly(true);
            editor.session.setMode('ace/mode/xml');
            editor.session.setValue(newXml);
        });

    };
    CloudCareDebuggerFormEntry.prototype = Object.create(CloudCareDebugger.prototype);
    CloudCareDebuggerFormEntry.prototype.constructor = CloudCareDebugger;
    // By default do nothing when updating the debugger
    CloudCareDebuggerFormEntry.prototype.onUpdate = function () {
        API.formattedQuestions(
            this.options.baseUrl,
            {
                session_id: this.options.formSessionId,
                username: this.options.username,
                restoreAs: this.options.restoreAs,
                domain: this.options.domain,
            }
        ).done(function (response) {
            this.formattedQuestionsHtml(response.formattedQuestions);
            readableForm.init();
            this.instanceXml(response.instanceXml);
            this.evalXPath.autocomplete(response.questionList);
            this.evalXPath.setRecentXPathQueries(response.recentXPathQueries || []);
            this.updating(false);
        }.bind(this));
    };

    var CloudCareDebuggerMenu = function (options) {
        var self = this;
        CloudCareDebugger.call(self, $.extend({ sessionType: SessionTypes.MENU }, options));
    };
    CloudCareDebuggerMenu.prototype = Object.create(CloudCareDebugger.prototype);
    CloudCareDebuggerMenu.prototype.constructor = CloudCareDebugger;
    CloudCareDebuggerMenu.prototype.onUpdate = function () {
        API.menuDebuggerContent(
            this.options.baseUrl,
            {
                selections: this.options.selections,
                query_data: this.options.queryData,
                username: this.options.username,
                restoreAs: this.options.restoreAs,
                domain: this.options.domain,
                app_id: this.options.appId,
            }
        ).done(function (response) {
            this.evalXPath.autocomplete(response.autoCompletableItems);
            this.evalXPath.setRecentXPathQueries(response.recentXPathQueries || []);
            this.updating(false);
        }.bind(this));
    };

    var DebugResponseLevel = function (label, key) {
        this.key = key;
        this.label = label;
    };

    var EvaluateXPath = function (options) {
        var self = this;
        self.options = options || {};
        _.defaults(self.options, {
            baseUrl: null,
            formSessionId: null,
            selections: null,
            queryData: null,
            username: null,
            restoreAs: null,
            domain: null,
            sessionType: SessionTypes.FORM,
            appId: null,
        });

        RegExp.escape = function (s) {
            return s.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
        };

        self.debugTraceOptions = ko.observableArray([
            new DebugResponseLevel("Output", "basic"),
            new DebugResponseLevel("Output + Eval Summary", "reduce"),
            new DebugResponseLevel("Output + Full Evaluation", "deep"),
        ]);
        self.xpath = ko.observable('');
        self.xpath = ko.observable('');
        self.selectedXPath = ko.observable('');
        self.selectedDebugOption = ko.observable('basic');

        self.maxLines = 50;

        self.fullResult = null;

        self.$xpath = null;
        self.newXPathQuery = function (data) {
            return {
                processedOutput: self.getBody(data.output),
                maxLines: self.maxLines,
                status: data.status,
                trace: self.getBody(data.trace),
                xpath: data.xpath,

                successResult: function () {
                    if (this.success()) {
                        return this.processedOutput[0];
                    }
                },
                getTruncatedSuccess: function () {
                    if (this.success()) {
                        return self.truncateResult(this.processedOutput[0], 5, true);
                    }
                },
                getFullSuccessResult: function () {
                    if (this.success()) {
                        return this.processedOutput[1];
                    }
                },
                isSuccessTruncated: function () {
                    return this.success() && this.processedOutput[1];
                },
                getMaxLines: function () {
                    return this.maxLines;
                },
                traceResult: function () {
                    if (this.success()) {
                        return this.trace[0];
                    }
                },
                isTraceTruncated: function () {
                    return this.hasTrace() && this.trace[1];
                },
                getFullTraceResult: function () {
                    if (this.hasTrace()) {
                        return this.trace[1];
                    }
                },
                hasTrace: function () {
                    return this.trace[0];
                },
                errorResult: function () {
                    if (!this.success()) {
                        if (this.processedOutput) {
                            return this.processedOutput[0];
                        }
                        return gettext('Error evaluating expression.');
                    }
                },
                success: function () {
                    return this.status === 'accepted';
                },
            };
        };
        self.xPathQuery = ko.observable(null);
        self.recentXPathQueries = ko.observableArray();
        self.setRecentXPathQueries = function (rawQueries) {
            self.recentXPathQueries(_.map(rawQueries, self.newXPathQuery));
        };

        var resultRegex = new RegExp(
            '^<[?]xml version="1.0" encoding="UTF-8"[?]>\\s*<result>\n*([\\s\\S]*?)\\s*</result>\\s*|' +
            '^<[?]xml version="1.0" encoding="UTF-8"[?]>\\s*<result/>()\\s*$');

        self.getBody = function (output) {
            if (!output) {
                return ['',''];
            }
            var inlineBody = self.formatResult(output);
            var numLines = (inlineBody.match(/\r?\n/g) || '').length + 1;
            var fullBody = '';
            if (numLines > self.maxLines) {
                fullBody = inlineBody;
                inlineBody = self.truncateResult(fullBody, self.maxLines, false);
            }
            return [inlineBody, fullBody];
        };

        self.formatResult = function (output) {
            return output.replace(resultRegex, "$1");
        };

        self.truncateResult = function (output, maxLines, addElipsis) {
            var items = output.split(RegExp("\r?\n")); // eslint-disable-line no-control-regex
            if (items.length > maxLines) {
                var toReturn = items.slice(0, maxLines).join("\n");
                if (addElipsis) {
                    return toReturn + "\n" + "...";
                }
                return toReturn;
            }
            return output;
        };

        self.onSubmitXPath = function () {
            self.evaluate(self.xpath());
        };

        self.onClickSelectedXPath = function () {
            if (self.selectedXPath()) {
                self.evaluate(self.selectedXPath());
                self.selectedXPath('');
            }
        };

        self.onClickSavedQuery = function (query) {
            self.xpath(query.xpath);
        };

        self.getSessionId = function () {
            if (self.options.sessionType === SessionTypes.FORM) {
                return self.options.formSessionId;
            }
        };

        self.evaluate = function (xpath) {
            API.evaluateXPath(
                self.options.baseUrl,
                {
                    session_id: self.getSessionId(),
                    username: self.options.username,
                    restoreAs: self.options.restoreAs,
                    domain: self.options.domain,
                    xpath: xpath,
                    app_id: self.options.appId,
                    selections: self.options.selections,
                    query_data: self.options.queryData,
                    debugOutput: self.selectedDebugOption().key,
                },
                self.options.sessionType
            ).done(function (response) {
                var xPathQuery = self.newXPathQuery({
                    status: response.status,
                    output: response.output,
                    trace: response.trace,
                    xpath: xpath,
                });
                self.xPathQuery(xPathQuery);
                self.recentXPathQueries.unshift(xPathQuery);
                // Ensure at the maximum we only show 6 queries
                self.recentXPathQueries(
                    self.recentXPathQueries.slice(0, 6)
                );
            });
            kissmetrics.track.event('[app-preview] User evaluated XPath');
        };

        self.onMouseUp = function () {
            var text = window.getSelection().toString();
            self.selectedXPath(text);
        };

        self.matcher = function (flag, subtext) {
            var match, regexp, currentQuery;
            // Match text that starts with the flag and then looks like a path.
            regexp = new RegExp('([\\s(]+|^)' + RegExp.escape(flag) + '([\\w/-]*)$', 'gi');
            match = regexp.exec(subtext);
            if (!match) {
                return null;
            }
            currentQuery = match[2];
            if (currentQuery.length < 2) {
                return null;
            }
            return currentQuery;
        };

        /**
         * Set autocomplete for xpath input.
         *
         * @param {Array} autocompleteData - List of questions to be autocompleted for the xpath input
         */
        self.autocomplete = function (autocompleteData) {
            self.$xpath = $('#xpath');
            self.$xpath.atwho('destroy');
            self.$xpath.atwho('setIframe', window.frameElement, true);
            self.$xpath.off('inserted.atwho');
            self.$xpath.on('inserted.atwho', function (atwhoEvent, $li) {
                var input = atwhoEvent.currentTarget;

                // Move cursor back one so we are inbetween the parenthesis
                if (input.setSelectionRange && $li.data().itemData.type === 'Function') {
                    input.setSelectionRange(input.selectionStart - 1, input.selectionStart - 1);
                }
            });
            self.$xpath.atwho({
                at: '',
                suffix: '',
                data: autocompleteData,
                searchKey: 'value',
                maxLen: Infinity,
                highlightFirst: false,
                displayTpl: function (d) {
                    var icon = getIconFromType(d.type);
                    return '<li><i class="' + icon + '"></i> ${value}</li>';
                },
                insertTpl: '${value}',
                callbacks: {
                    matcher: self.matcher,
                },
            });
        };
    };

    var getIconFromType = function (type) {
        var icon = {
            'Trigger': 'fcc fcc-fd-variable',
            'Text': 'fcc fcc-fd-text',
            'PhoneNumber': 'fa fa-signal',
            'Secret': 'fa fa-key',
            'Integer': 'fcc fcc-fd-numeric',
            'Audio': 'fcc fcc-fd-audio-capture',
            'Image': 'fa fa-camera',
            'Video': 'fa fa-video-camera',
            'Signature': 'fcc fcc-fd-signature',
            'Geopoint': 'fa-solid fa-location-dot',
            'Barcode Scan': 'fa fa-barcode',
            'Date': 'fa-solid fa-calendar-days',
            'Date and Time': 'fcc fcc-fd-datetime',
            'Time': 'fa-regular fa-clock',
            'Select': 'fcc fcc-fd-single-select',
            'Double': 'fcc fcc-fd-decimal',
            'Label': 'fa fa-tag',
            'MSelect': 'fcc fcc-fd-multi-select',
            'Multiple Choice': 'fcc fcc-fd-single-select',
            'Group': 'fa fa-folder-open',
            'Question List': 'fa fa-reorder',
            'Repeat Group': 'fa fa-retweet',
            'Function': 'fa fa-calculator',
        }[type];
        return icon || '';
    };

    var API = {
        evaluateXPath: function (url, params, sessionType) {
            var action = sessionType === SessionTypes.MENU ? 'evaluate-menu-xpath' : 'evaluate-xpath';
            return API.request(url, action, params);
        },
        formattedQuestions: function (url, params) {
            return API.request(url, 'formatted_questions', params);
        },
        menuDebuggerContent: function (url, params) {
            return API.request(url, 'menu_debugger_content', params);
        },
        request: function (url, action, params) {
            params['tz_offset_millis'] = (new Date()).getTimezoneOffset() * 60 * 1000 * -1;
            params['tz_from_browser'] = Intl.DateTimeFormat().resolvedOptions().timeZone;
            return $.ajax({
                type: 'POST',
                url: url + "/" + action,
                data: JSON.stringify(params),
                contentType: "application/json",
                dataType: "json",
                crossDomain: {crossDomain: true},
                xhrFields: {withCredentials: true},
            });
        },
    };

    _.delay(function () {
        ko.bindingHandlers.aceEditor = {
            init: function (element, valueAccessor) {
                var editor = ace.edit(element, {
                    showGutter: false,      // no line numbers
                    showPrintMargin: false,
                    maxLines: 10,
                    minLines: 1,
                    fontSize: 14,
                    wrap: true,
                    useWorker: false,
                });
                editor.setReadOnly(true);
                editor.session.setMode('ace/mode/xml');
                editor.session.setValue(ko.unwrap(valueAccessor()));
                element.editor = editor;
            },
            update: function (element, valueAccessor) {
                var observedValue = ko.unwrap(valueAccessor());
                if (element.editor) {
                    element.editor.session.setValue(observedValue);
                }
            },
        };
        ko.bindingHandlers.clipboardButton = {
            init: function (element, valueAccessor) {
                new Clipboard(element,
                    {
                        text: function () {
                            return ko.unwrap(valueAccessor());
                        },
                    });
            },
        };

    });

    return {
        CloudCareDebuggerFormEntry: CloudCareDebuggerFormEntry,
        CloudCareDebuggerMenu: CloudCareDebuggerMenu,
        EvaluateXPath: EvaluateXPath,
        TabIDs: TabIDs,
        API: API,
    };

});
