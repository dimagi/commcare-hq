/* globals hqDefine */
hqDefine('userreports/js/expression_evaluator', function () {
    var expressionModel = function (editor, submitUrl, initialData) {
        var self = {};
        initialData = initialData || {};
        self.editor = editor;
        self.submitUrl = submitUrl;
        self.documentType = ko.observable(initialData.documentType);
        self.documentId = ko.observable(initialData.documentId);
        self.dataSourceId = ko.observable(initialData.dataSourceId);
        self.expressionText = ko.observable(editor.getSession().getValue());
        self.uiFeedback = ko.observable();

        self.getExpressionJSON = function () {
            try {
                return JSON.parse(self.expressionText());
            } catch (err) {
                return null;
            }
        };
        self.editor.getSession().on('change', function () {
            self.expressionText(self.editor.getSession().getValue());
        });

        self.hasError = ko.computed(function () {
            return self.getExpressionJSON() === null;
        }, self);

        self.updateUrl = function () {
            var currentParams = document.location.search.substring(1);
            var newParams = {
                'id': self.documentId(),
                'type': self.documentType(),
            };
            if (self.dataSourceId()) {
                newParams['data_source'] = self.dataSourceId();
            }
            newParams = $.param(newParams);
            if (currentParams !== newParams) {
                var newUrl = document.location.pathname + "?" + newParams;
                if (history.pushState) {
                    window.history.pushState(null, '', newUrl);
                }
            }
        };

        self.evaluateExpression = function () {
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
                        data_source: self.dataSourceId(),
                        expression: self.expressionText(),
                    },
                    success: function (data) {
                        self.uiFeedback("<strong>Result:</strong> " + JSON.stringify(data.result));
                        self.updateUrl();
                    },
                    error: function (data) {
                        self.uiFeedback("<strong>Failure!:</strong> " + data.responseJSON ? data.responseJSON.error : "Unknown error");
                    },
                });
            }
        };
        return self;
    };
    return {expressionModel: expressionModel};
});
