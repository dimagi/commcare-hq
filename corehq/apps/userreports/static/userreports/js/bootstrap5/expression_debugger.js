import "commcarehq";
import $ from "jquery";
import baseAce from "hqwebapp/js/base_ace";
import initialPageData from "hqwebapp/js/initial_page_data";
import expressionModel from "userreports/js/expression_evaluator";
import "hqwebapp/js/bootstrap5/widgets";
import "hqwebapp/js/components/select_toggle";

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
