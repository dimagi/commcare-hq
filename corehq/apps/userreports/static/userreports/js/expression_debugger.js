/* globals ace */
hqDefine('userreports/js/expression_debugger', function () {
    $(function () {
        var expressionModel = hqImport('userreports/js/expression_evaluator').expressionModel;
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        var submitUrl = initialPageData.reverse("expression_evaluator");
        var expressionEditor = ace.edit($('#expression ~pre')[0]);
        var docEditor = ace.edit($('#raw_document ~pre')[0]);
        docEditor.getSession().setValue("{}");
        var sampleExpression = {
            "type": "property_name",
            "property_name": "name",
        };
        var sampleText = JSON.stringify(sampleExpression, null, 2);
        expressionEditor.getSession().setValue(sampleText);
        var initialData = {
            inputType: initialPageData.get('input_type'),
            documentType: initialPageData.get('document_type'),
            documentId: initialPageData.get('document_id'),
            dataSourceId: initialPageData.get('data_source_id'),
            ucrExpressionId: initialPageData.get('ucr_expression_id'),
        };
        $('#expression-debugger').koApplyBindings(
            expressionModel(expressionEditor, docEditor, submitUrl, initialData)
        );
    });
});
