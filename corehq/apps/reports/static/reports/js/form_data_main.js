hqDefine("reports/js/form_data_main", function() {
    $(function() {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
        hqImport("reports/js/single_form").initSingleForm(
            initial_page_data("xform_id"),
            initial_page_data("question_response_map"),
            initial_page_data("ordered_question_values")
        );
    });
});
