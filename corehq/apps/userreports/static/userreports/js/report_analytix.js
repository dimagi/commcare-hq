import $ from "jquery";
import googleAnalytics from "analytix/js/google";
import noopMetrics from "analytix/js/noopMetrics";

var trackReportBuilder = googleAnalytics.trackCategory("Report Builder v2");
$(function () {
    $('#js-click-preview-subscribe').click(function () {
        noopMetrics.track.event("RBv2 - Clicks on Subscribe Link in Preview Message Bar");
    });

    $('#create-new-report-left-nav').click(function () {
        var analyticsLabel = $(this).hasClass('preview') ? 'Preview' : 'HasAccess';
        trackReportBuilder.event('Create New Report', analyticsLabel);
    });
});
export default {
    track: trackReportBuilder,
};
