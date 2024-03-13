hqDefine('userreports/js/report_analytix', function () {
    var trackReportBuilder = hqImport('analytix/js/google').trackCategory("Report Builder v2");
    $(function () {
        $('#js-click-preview-subscribe').click(function () {
            hqImport('analytix/js/kissmetrix').track.event("RBv2 - Clicks on Subscribe Link in Preview Message Bar");
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
