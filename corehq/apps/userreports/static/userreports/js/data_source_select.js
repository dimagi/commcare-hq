hqDefine("userreports/js/data_source_select", [
    'jquery',
    'analytix/js/kissmetrix',
    'hqwebapp/js/bootstrap3/main',
    'userreports/js/data_source_select_model',
    'userreports/js/report_analytix',
    'commcarehq',
], function (
    $,
    kissmetrics,
    hqMain,
    dataModel,
    analytics,
) {
    $(function () {
        $("#report-builder-form").koApplyBindings(dataModel);
        $('#js-next-data-source').click(function () {
            analytics.track.event('Data Source Next', hqMain.capitalize(dataModel.sourceType()));
            kissmetrics.track.event("RBv2 - Data Source");
        });
    });
});
