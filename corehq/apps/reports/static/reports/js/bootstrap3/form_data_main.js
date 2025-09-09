import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import singleForm from "reports/js/bootstrap3/single_form";
import noopMetrics from "analytix/js/noopMetrics";

$(function () {
    singleForm.initSingleForm({
        instance_id: initialPageData.get("xform_id"),
        form_question_map: initialPageData.get("question_response_map"),
        ordered_question_values: initialPageData.get("ordered_question_values"),
    });
});

noopMetrics.track.event('Viewed Form Submission');
