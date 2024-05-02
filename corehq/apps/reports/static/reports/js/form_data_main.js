hqDefine("reports/js/form_data_main", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "reports/js/bootstrap3/single_form",
    "analytix/js/kissmetrix",
], function (
    $,
    initialPageData,
    singleForm,
    kissmetrics
) {
    $(function () {
        singleForm.initSingleForm({
            instance_id: initialPageData.get("xform_id"),
            form_question_map: initialPageData.get("question_response_map"),
            ordered_question_values: initialPageData.get("ordered_question_values"),
        });
    });

    kissmetrics.track.event('Viewed Form Submission');
});
