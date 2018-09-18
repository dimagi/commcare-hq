hqDefine("reports/js/form_data_main", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "reports/js/single_form",
], function (
    $,
    initialPageData,
    singleForm
) {
    $(function () {
        singleForm.initSingleForm({
            instance_id: initialPageData.get("xform_id"),
            form_question_map: initialPageData.get("question_response_map"),
            ordered_question_values: initialPageData.get("ordered_question_values"),
        });
    });
});
