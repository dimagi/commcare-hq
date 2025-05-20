import "commcarehq";
import $ from "jquery";
import kissmetrics from "analytix/js/kissmetrix";
import hqMain from "hqwebapp/js/bootstrap3/main";
import dataModel from "userreports/js/data_source_select_model";
import analytics from "userreports/js/report_analytix";

$(function () {
    $("#report-builder-form").koApplyBindings(dataModel);
    $('#js-next-data-source').click(function () {
        analytics.track.event('Data Source Next', hqMain.capitalize(dataModel.sourceType()));
        kissmetrics.track.event("RBv2 - Data Source");
    });
});
