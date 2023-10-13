hqDefine("reports/js/filters/case_list_explorer_knockout_bindings", ['jquery', 'underscore', 'knockout', 'hqwebapp/js/atwho', 'ace-builds/src-min-noconflict/ace'], function ($, _, ko, atwho, ace) {

    ko.bindingHandlers.xPathAutocomplete = {
        init: function (element, valueAccessor, allBindings, viewModel) {
            var $element = $(element),
                editor = ace.edit(
                    element,
                    {
                        enableLiveAutocompletion: true,
                        showPrintMargin: false,
                        showLineNumbers: false,
                        showFoldWidgets: false,
                        showGutter: false,
                        highlightGutterLine: false,
                        highlightActiveLine: false,
                        maxLines: 30,
                        minLines: 3,
                        fontSize: 13,
                        wrap: true,
                        indentedSoftWrap: false,
                        useWorker: false, // enable the worker to show syntax errors
                    }
                );
            editor.session.setMode('ace/mode/xquery'); // does reasonable syntax highlighting for XPath

            var updateKOModel = function () {
                viewModel.query(editor.getValue());
                $element.parent().trigger('change');
            };
            editor.on('change', function () {
                updateKOModel();
            });
            updateKOModel();

            // Set placeholder
            function update() {
                // https://stackoverflow.com/a/26700324/2957657
                var shouldShow = !editor.session.getValue().length,
                    node = editor.renderer.emptyMessageNode;
                if (!shouldShow && node) {
                    editor.renderer.scroller.removeChild(editor.renderer.emptyMessageNode);
                    editor.renderer.emptyMessageNode = null;
                } else if (shouldShow && !node) {
                    node = editor.renderer.emptyMessageNode = document.createElement("div");
                    node.textContent = gettext("e.g. (dob <= '2017-02-01' and initial_home_visit_completed = 'yes') ");
                    node.className = "ace_invisible ace_emptyMessage";
                    node.style.padding = "0 9px";
                    editor.renderer.scroller.appendChild(node);
                }
            }
            editor.on("input", update);
            setTimeout(update, 100);
        },
        update: function (element, valueAccessor) {
            var caseProperties = ko.utils.unwrapObservable(valueAccessor());
            var casePropertyAutocomplete = {
                getCompletions: function (editor, session, pos, prefix, callback) {
                    var currentValue = editor.getValue(),
                        newPopupWidth = 0,
                        popup = editor.completer.getPopup(),
                        leftQuotesSingle = (currentValue.substr(0, pos.column).match(/'/g) || []).length,
                        leftQuotesDouble = (currentValue.substr(0, pos.column).match(/"/g) || []).length,
                        insideQuote = leftQuotesSingle && (leftQuotesSingle % 2 !== 0) || leftQuotesDouble && (leftQuotesDouble % 2 !== 0);
                    if (insideQuote) {
                        // don't autocomplete case properties when inside a quote
                        return;
                    }
                    callback(null, _.map(caseProperties, function (suggestion) {
                        var currentLabelLength = suggestion.name.length,
                            metaText = suggestion.case_type || suggestion.meta_type,
                            currentMetaLength = metaText ? metaText.length : 0,
                            minPopupWidth = currentLabelLength * 6.5 + currentMetaLength * 5.2;
                        if (minPopupWidth > newPopupWidth) {
                            newPopupWidth = minPopupWidth;
                        }
                        return {
                            name: suggestion.name,
                            value: suggestion.name,
                            meta: suggestion.case_type || suggestion.meta_type,
                        };
                    }));
                    popup.container.style.width = Math.ceil(newPopupWidth) + "px";
                    popup.resize();
                },
            };
            ace.require("ace/ext/language_tools").setCompleters([casePropertyAutocomplete]);
        },
    };

    ko.bindingHandlers.explorerColumnsAutocomplete = {
        init: function (element) {
            var $element = $(element);
            if (!$element.atwho) {
                throw new Error("The typeahead binding requires Atwho.js and Caret.js");
            }

            atwho.init($element, {
                atwhoOptions: {
                    displayTpl: function (item) {
                        if (item.case_type) {
                            return '<li><span class="label label-default">${case_type}</span> ${name}</li>';
                        }
                        return '<li><span class="label label-primary">${meta_type}</span> ${name}</li>';
                    },
                },
                afterInsert: function () {
                    $element.trigger('textchange');
                },
            });

            $element.on("textchange", function () {
                if ($element.val()) {
                    $element.change();
                }
            });
        },

        update: function (element, valueAccessor) {
            $(element).atwho('load', '', ko.utils.unwrapObservable(valueAccessor()));
        },
    };

    return {
        xPathAutocomplete: ko.bindingHandlers.xPathAutocomplete,
        explorerColumnsAutocomplete: ko.bindingHandlers.explorerColumnsAutocomplete,
    };
});
