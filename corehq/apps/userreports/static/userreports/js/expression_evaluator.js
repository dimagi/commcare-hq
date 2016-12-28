/* globals hqDefine */
hqDefine('userreports/js/expression_evaluator.js', function () {
    var ExpressionModel = function (editor, submitUrl, initialData) {
        var self = this;
        initialData = initialData || {};
        self.editor = editor;
        self.submitUrl = submitUrl;
        self.documentType = ko.observable(initialData.documentType);
        self.documentId = ko.observable(initialData.documentId);
        self.expressionText = ko.observable(editor.getValue());
        self.uiFeedback = ko.observable();

        self.getExpressionJSON = function () {
            try {
                return JSON.parse(self.expressionText());
            } catch (err) {
                return null;
            }
        };
        self.editor.on('change', function () {
            self.expressionText(self.editor.getValue());
        });

        self.hasError = ko.computed(function () {
            return self.getExpressionJSON() === null;
        }, self);

        self.updateUrl = function () {
            var currentParams = document.location.search.substring(1);
            var newParams = $.param({
                'id': self.documentId(),
                'type': self.documentType(),
            });
            if (currentParams !== newParams) {
                var newUrl = document.location.pathname + "?" + newParams;
                if (history.pushState) {
                    window.history.pushState(null, '', newUrl);
                }
            }
        };

        self.evaluateExpression = function() {
            self.uiFeedback("");
            if (self.hasError()) {
                self.uiFeedback("Please fix all parsing errors before evaluating.");
            } else if (!self.documentId()) {
                self.uiFeedback("Please enter a document ID.");
            }
            else {
                $.post({
                    url: self.submitUrl,
                    data: {
                        doc_type: self.documentType(),
                        doc_id: self.documentId(),
                        expression: self.expressionText(),
                    },
                    success: function (data) {
                        self.uiFeedback("<strong>Result:</strong> " + JSON.stringify(data.result));
                        self.updateUrl();
                    },
                    error: function (data) {
                        self.uiFeedback("<strong>Failure!:</strong> " + data.responseJSON.error);
                    },
                });
            }
        };
    };
    return {ExpressionModel: ExpressionModel};
});
