hqDefine('userreports/js/bootstrap5/expression_debugger', [
    "jquery",
    "underscore",
    "hqwebapp/js/base_ace",
    "hqwebapp/js/initial_page_data",
    "userreports/js/expression_evaluator",
    "hqwebapp/js/bootstrap5/widgets",
    "hqwebapp/js/components/select_toggle",
    "commcarehq",
], function (
    $,
    _,
    baseAce,
    initialPageData,
    expressionModel,
) {
    $(function () {
        var submitUrl = initialPageData.reverse("expression_evaluator");
        var expressionEditor = baseAce.initJsonWidget($("#expression"));
        var docEditor = baseAce.initJsonWidget($("#raw_document"));
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
            expressionModel.expressionModel(expressionEditor, docEditor, submitUrl, initialData),
        );
    });
});
