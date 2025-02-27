hqDefine("reports/js/charts/pie_chart", [
    'jquery',
    'd3/d3.min',
    'nvd3/nv.d3.min',
    'nvd3/src/nv.d3.css',
], function (
    $,
    d3,
    nv,
) {
    var init = function (data) {
        nv.addGraph(function () {
            var chartConfig = data.configDict,
                chartData = data.chartData,
                chartId = '#' + data.chartId;

            $(chartId).show();

            var chart = nv.models.pieChart()
                .x(function (d) { return d.label; })
                .y(function (d) { return d.value; });

            chart.showLabels(chartConfig.showLabels);
            chart.donut(chartConfig.donut);
            chart.tooltips(chartConfig.tooltips);
            chart.margin(chartConfig.margin);
            if (chartConfig.color.length !== 0) {
                chart.color(chartConfig.color);
            }

            d3.select(chartId + ' svg')
                .datum(chartData)
                .transition().duration(500).call(chart);

            nv.utils.windowResize(chart.update);

            return chart;
        });
    };

    return { init: init };
});
