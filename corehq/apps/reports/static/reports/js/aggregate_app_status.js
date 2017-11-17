/* globals d3, django, moment, nv */
hqDefine("reports/js/aggregate_app_status", function() {
    function setupCharts(data, div) {
        nv.addGraph(function() {
        var chart = nv.models.multiBarChart()
          .transitionDuration(350)
          .showControls(false)
          .reduceXTicks(true)
          .rotateLabels(0)
          .groupSpacing(0.1)
        ;

        chart.yAxis
            .tickFormat(d3.format(',f'));

        d3.select('#' + div + ' svg')
            .datum([data])
            .call(chart);

        nv.utils.windowResize(chart.update);
        return chart;
    });

    }
    $(document).ajaxSuccess(function(event, xhr, settings) {
        if (settings.url.match(/reports\/async\/aggregate_user_status/)) {
            setupCharts($("#submission-data").data("value"), 'submission_dates');
            setupCharts($("#submission-totals").data("value"), 'submission_totals');
            setupCharts($("#sync-data").data("value"), 'sync_dates');
            setupCharts($("#sync-totals").data("value"), 'sync_totals');
        }
    });
});
