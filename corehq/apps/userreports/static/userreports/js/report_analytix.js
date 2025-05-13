import $ from "jquery";
import googleAnalytics from "analytix/js/google";
import kissmetricsAnalytics from "analytix/js/kissmetrix";

var trackReportBuilder = googleAnalytics.trackCategory("Report Builder v2");
$(function () {
    $('#js-click-preview-subscribe').click(function () {
        kissmetricsAnalytics.track.event("RBv2 - Clicks on Subscribe Link in Preview Message Bar");
    });

    $('#create-new-report-left-nav').click(function () {
        var analyticsLabel = $(this).hasClass('preview') ? 'Preview' : 'HasAccess';
        trackReportBuilder.event('Create New Report', analyticsLabel);
    });
});
export default {
    track: trackReportBuilder,
};
