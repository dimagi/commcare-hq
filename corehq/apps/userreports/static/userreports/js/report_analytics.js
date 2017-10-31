/* globals $ */
hqDefine('userreports/js/report_analytics', function() {
    $(function () {
        $('#js-click-preview-subscribe').click(function () {
            kmqPushSafe(["trackClick", "rbv2_subscribe_link_preview", "RBv2 - Clicks on Subscribe Link in Preview Message Bar"]);
        });

        $('#create-new-report-left-nav').click(function () {
            var analyticsLabel = $(this).hasClass('preview') ? 'Preview' : 'HasAccess';
            window.analytics.usage('Report Builder v2', 'Create New Report', analyticsLabel);
        });
    });
});
