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
        self.editor.getSession().on('change', function () {
            self.expressionText(self.editor.getSession().getValue());
        });

        self.hasParseError = ko.computed(function () {
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
            self.error("");
            self.result("");
            if (self.hasParseError()) {
                return;
            } else if (!self.documentId()) {
                self.error("Please enter a document ID.");
            }
            else {
                self.isEvaluating(true);
                $.post({
                    url: self.submitUrl,
                    data: {
                        doc_type: self.documentType(),
                        doc_id: self.documentId(),
                        data_source: self.dataSourceId(),
                        expression: self.expressionText(),
                    },
                    success: function (data) {
                        self.result(JSON.stringify(data.result));
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
