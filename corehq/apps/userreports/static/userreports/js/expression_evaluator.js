hqDefine('userreports/js/expression_evaluator', function () {
    var expressionModel = function (expressionEditor, docEditor, submitUrl, initialData) {
        var self = {};
        initialData = initialData || {};
        self.expressionEditor = expressionEditor;
        self.docEditor = docEditor;
        self.submitUrl = submitUrl;
        self.inputType = ko.observable(initialData.inputType);
        self.documentType = ko.observable(initialData.documentType);
        self.documentId = ko.observable(initialData.documentId);
        self.dataSourceId = ko.observable(initialData.dataSourceId);
        self.ucrExpressionId = ko.observable(initialData.ucrExpressionId);
        self.expressionText = ko.observable(expressionEditor.getSession().getValue());
        self.docText = ko.observable(docEditor.getSession().getValue());
        self.error = ko.observable();
        self.result = ko.observable();
        self.isEvaluating = ko.observable(false);

        self.getExpressionJSON = function () {
            try {
                return JSON.parse(self.expressionText());
            } catch (err) {
                return null;
            }
        };
        self.expressionEditor.getSession().on('change', function () {
            self.expressionText(self.expressionEditor.getSession().getValue());
        });

        self.getDocJSON = function () {
            try {
                return JSON.parse(self.docText());
            } catch (err) {
                return null;
            }
        };
        self.docEditor.getSession().on('change', function () {
            self.docText(self.docEditor.getSession().getValue());
        });

        self.hasParseError = ko.computed(function () {
            return self.getExpressionJSON() === null;
        }, self);

        self.hasDocParseError = ko.computed(function () {
            return self.getDocJSON() === null;
        }, self);

        self.formatJson = function () {
            let expr = self.getExpressionJSON();
            if (expr !== null) {
                self.expressionEditor.getSession().setValue(JSON.stringify(expr, null, 2));
            }

            let doc = self.getDocJSON();
            if (doc !== null) {
                self.docEditor.getSession().setValue(JSON.stringify(doc, null, 2));
            }
        };

        self.updateUrl = function () {
            var currentParams = document.location.search.substring(1);
            var newParams = {
                'id': self.documentId(),
                'input_type': self.inputType(),
                'type': self.documentType(),
            };
            if (self.dataSourceId()) {
                newParams['data_source'] = self.dataSourceId();
            }
            if (self.ucrExpressionId()) {
                newParams['ucr_expression_id'] = self.ucrExpressionId();
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
            self.error("");
            self.result("");
            if (self.hasParseError() || self.hasDocParseError()) {
                return;
            } else if (!self.documentId() && !self.docText()) {
                self.error("Please enter a document ID or document JSON");
            } else {
                self.isEvaluating(true);
                let data = {
                    input_type: self.inputType(),
                    data_source: self.dataSourceId(),
                };
                if (self.ucrExpressionId()) {
                    data.ucr_expression_id = self.ucrExpressionId();
                } else {
                    data.expression = self.expressionText();
                }
                if (self.inputType() === 'doc') {
                    data.doc_type = self.documentType();
                    data.doc_id = self.documentId();
                } else {
                    data.raw_doc = self.docText();
                }
                $.post({
                    url: self.submitUrl,
                    data: data,
                    success: function (data) {
                        self.result(JSON.stringify(data.result, null, 4));
                        self.updateUrl();
                        self.isEvaluating(false);
                    },
                    error: function (data) {
                        self.error(data.responseJSON ? data.responseJSON.error : gettext("Unknown error"));
                        self.isEvaluating(false);
                    },
                });
            }
        };
        return self;
    };
    return {expressionModel: expressionModel};
});
