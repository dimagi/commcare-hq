/* globals d3, django, moment, nv */
hqDefine("reports/js/aggregate_app_status", function() {
    function setupCharts(data, div) {
        nv.addGraph(function() {
        var chart = nv.models.multiBarChart()
          .transitionDuration(350)
          .reduceXTicks(true)   //If 'false', every single x-axis tick label will be rendered.
          .rotateLabels(0)      //Angle to rotate x-axis labels.
          .showControls(true)   //Allow user to switch between 'Grouped' and 'Stacked' mode.
          .groupSpacing(0.1)    //Distance between each group of bars.
        ;

        chart.xAxis
            .tickFormat(d3.format(',f'));

        chart.yAxis
            .tickFormat(d3.format(',.1f'));

        //    var data = exampleData();
        console.log(data);
        d3.select('#' + div + ' svg')
            .datum([data])
            .call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    });

    }
    $(document).ajaxSuccess(function(event, xhr, settings) {
        if (settings.url.match(/reports\/async\/aggregate_app_status/)) {
            setupCharts($("#submission-data").data("value"), 'submission_dates');
            setupCharts($("#sync-data").data("value"), 'sync_dates');

        }
    });
});
