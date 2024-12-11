hqDefine('userreports/js/report_analytix', [
    'jquery',
    'analytix/js/google',
    'analytix/js/kissmetrix',
], function (
    $,
    googleAnalytics,
    kissmetrics,
) {
    var trackReportBuilder = googleAnalytics.trackCategory("Report Builder v2");
    $(function () {
        $('#js-click-preview-subscribe').click(function () {
            kissmetrics.track.event("RBv2 - Clicks on Subscribe Link in Preview Message Bar");
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
