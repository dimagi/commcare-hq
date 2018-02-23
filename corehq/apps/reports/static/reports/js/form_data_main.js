hqDefine("reports/js/form_data_main", function() {
    $(function() {
        hqImport("reports/js/single_form").initSingleForm(hqImport("hqwebapp/js/initial_page_data").get("question_response_map"));
    });
});
