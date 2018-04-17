hqDefine("reports/js/form_data_main", function() {
    $(function() {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
        hqImport("reports/js/single_form").initSingleForm({
            instance_id: initialPageData("xform_id"),
            form_question_map: initialPageData("question_response_map"),
            ordered_question_values: initialPageData("ordered_question_values"),
        });
    });
});
