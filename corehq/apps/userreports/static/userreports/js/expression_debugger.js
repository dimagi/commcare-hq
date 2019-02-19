/* globals ace */
hqDefine('userreports/js/expression_debugger', function () {
    $(function () {
        var expressionModel = hqImport('userreports/js/expression_evaluator').expressionModel;
        var submitUrl = hqImport("hqwebapp/js/initial_page_data").reverse("expression_evaluator");
        var expressionEditor = ace.edit($('.jsonwidget ~pre')[0]);
        var sampleExpression = {
            "type": "property_name",
            "property_name": "name",
        };
        var sampleText = JSON.stringify(sampleExpression, null, 2);
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
        expressionEditor.getSession().setValue(sampleText);
        var initialData = {
            documentType: initial_page_data('document_type'),
            documentId: initial_page_data('document_id'),
            dataSourceId: initial_page_data('data_source_id'),
        };
        ko.applyBindings(
            expressionModel(expressionEditor, submitUrl, initialData),
            document.getElementById('expression-debugger')
        );
    });
});
