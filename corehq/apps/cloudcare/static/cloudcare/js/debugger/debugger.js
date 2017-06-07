/* globals CodeMirror */
hqDefine('cloudcare/js/debugger/debugger.js', function () {
    var CloudCareDebugger = function(options) {
        var self = this;
        self.options = options || {};

        self.evalXPath = new EvaluateXPath();
        self.isMinimized = ko.observable(true);
        self.instanceXml = ko.observable('');
        self.formattedQuestionsHtml = ko.observable('');

        // Whether or not the debugger is in the middle of updating from an ajax request
        self.updating = ko.observable(false);

        self.toggleState = function() {
            self.isMinimized(!self.isMinimized());
            // Wait to set the content heigh until after the CSS animation has completed.
            // In order to support multiple heights, we set the height with javascript since
            // a div inside a fixed position element cannot scroll unless a height is explicitly set.
            setTimeout(self.setContentHeight, 1001);

            if (!self.isMinimized()) {
                self.updating(true);
                /* TODO
                 Call to update debugger
                 .done(function(response) {
                    self.onUpdateDebugger();
                });
                */
            }
            window.analytics.workflow('[app-preview] User toggled CloudCare debugger');
        };
        self.collapseNavbar = function() {
            $('.navbar-collapse').collapse('hide');
        };

        self.afterRender = function() {
            self.evalXPath.afterRender();
        };

        self.updateDebugger = function(resp) {
            self.updating(false);
            self.formattedQuestionsHtml(resp.formattedQuestions);
            self.instanceXml(resp.instanceXml);
            self.evalXPath.autocomplete(resp.questionList);
            self.evalXPath.recentXPathQueries(resp.recentXPathQueries || []);
        };

        self.setContentHeight = function() {
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

        self.instanceXml.subscribe(function(newXml) {
            var codeMirror,
                $instanceTab = $('#debugger-xml-instance-tab');

            codeMirror = CodeMirror(function(el) {
                $('#xml-viewer-pretty').html(el);
            }, {
                value: newXml,
                mode: 'xml',
                viewportMargin: Infinity,
                readOnly: true,
                lineNumbers: true,
            });
            $instanceTab.off('shown.bs.tab');
            $instanceTab.on('shown.bs.tab', function() {
                codeMirror.refresh();
            });
        });

        // Called afterRender, ensures that the debugger takes the whole screen
        self.adjustWidth = function() {
            var $debug = $('#instance-xml-home'),
                $body = $('body');

            $debug.width($body.width());
        };
    };

    var EvaluateXPath = function() {
        var self = this;
        self.xpath = ko.observable('');
        self.selectedXPath = ko.observable('');
        self.recentXPathQueries = ko.observableArray();
        self.$xpath = null;
        self.codeMirrorResult = null;
        self.result = ko.observable('');
        self.success = ko.observable(true);
        self.onSubmitXPath = function() {
            self.evaluate(self.xpath());
        };
        self.onClickSelectedXPath = function() {
            if (self.selectedXPath()) {
                self.evaluate(self.selectedXPath());
                self.selectedXPath('');
            }
        };
        self.onClickSavedQuery = function(query) {
            self.xpath(query.xpath);
        };
        self.evaluate = function(xpath) {
            /* TODO
             Call to evaluate xpath
             .done(function(response) {
                var callback = function(response) {
                    self.result(response.output);
                    self.success(response.status === "accepted");
                };
            });
            */
            window.analytics.workflow('[app-preview] User evaluated XPath');
        };

        self.afterRender = function() {
            var options = {
                mode: 'xml',
                viewportMargin: Infinity,
                readOnly: true,
                lineNumbers: true,
            };
            self.codeMirrorResult = CodeMirror.fromTextArea($('#evaluate-result')[0], options);
        }

        self.result.subscribe(function(newResult) {
            self.codeMirrorResult.setValue(newResult);
        });

        self.isSuccess = function(query) {
            return query.status === 'accepted';
        };

        self.onMouseUp = function() {
            var text = window.getSelection().toString();
            self.selectedXPath(text);
        };

        self.matcher = function(flag, subtext) {
            var match, regexp, currentQuery;
            // Match text that starts with the flag and then looks like a path.
            regexp = new RegExp('([\\s\(]+|^)' + RegExp.escape(flag) + '([\\w/-]*)$', 'gi');
            match = regexp.exec(subtext);
            if (!match) {
                return null;
            }
            currentQuery = match[2]
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
        self.autocomplete = function(autocompleteData) {
            self.$xpath = $('#xpath');
            self.$xpath.atwho('destroy');
            self.$xpath.atwho('setIframe', window.frameElement, true);
            self.$xpath.off('inserted.atwho');
            self.$xpath.on('inserted.atwho', function(atwhoEvent, $li, e) {
                var input = atwhoEvent.currentTarget

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
                displayTpl: function(d) {
                    var icon = Formplayer.Utils.getIconFromType(d.type);
                    return '<li><i class="' + icon + '"></i> ${value}</li>';
                },
                insertTpl: '${value}',
                callbacks: {
                    matcher: self.matcher,
                },
            });
        };
    };

    return {
        CloudCareDebugger: CloudCareDebugger,
    };

})
