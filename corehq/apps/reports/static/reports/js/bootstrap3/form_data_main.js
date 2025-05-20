import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import singleForm from "reports/js/bootstrap3/single_form";
import kissmetrics from "analytix/js/kissmetrix";

$(function () {
    singleForm.initSingleForm({
        instance_id: initialPageData.get("xform_id"),
        form_question_map: initialPageData.get("question_response_map"),
        ordered_question_values: initialPageData.get("ordered_question_values"),
    });
});

kissmetrics.track.event('Viewed Form Submission');
