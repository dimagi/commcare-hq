hqDefine('userreports/js/expression_debugger.js', function() {
    $(function () {
        var ExpressionModel = hqImport('userreports/js/expression_evaluator.js').ExpressionModel;
        var submitUrl = hqImport("hqwebapp/js/urllib.js").reverse("expression_evaluator");
        var expressionEditor = $('.CodeMirror')[0].CodeMirror;  // http://stackoverflow.com/a/24987585/8207
        var sampleExpression = {
            "type": "property_name",
            "property_name": "name",
        };
        var sampleText = JSON.stringify(sampleExpression, null, 2);
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
        expressionEditor.setValue(sampleText);
        var initialData = {
            documentType: initial_page_data('document_type'),
            documentId: initial_page_data('document_id'),
            dataSourceId: initial_page_data('data_source_id'),
        };
        ko.applyBindings(
            new ExpressionModel(expressionEditor, submitUrl, initialData),
            document.getElementById('expression-debugger')
        );
    });
});
