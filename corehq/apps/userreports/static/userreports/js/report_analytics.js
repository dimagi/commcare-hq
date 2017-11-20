/* globals $, kmqPushSafe */

hqDefine('userreports/js/report_analytics', function() {
    var trackReportBuilder = hqImport('analytics/js/google').trackCategory("Report Builder v2");
    $(function () {
        $('#js-click-preview-subscribe').click(function () {
            kmqPushSafe(["trackClick", "rbv2_subscribe_link_preview", "RBv2 - Clicks on Subscribe Link in Preview Message Bar"]);
        });

        $('#create-new-report-left-nav').click(function () {
            var analyticsLabel = $(this).hasClass('preview') ? 'Preview' : 'HasAccess';
            trackReportBuilder.event('Create New Report', analyticsLabel);
        });
    });
    return {
        track: trackReportBuilder,
    };
});
