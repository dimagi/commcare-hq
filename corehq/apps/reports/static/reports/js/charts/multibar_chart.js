hqDefine('reports/js/charts/multibar_chart', [
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
                chartId = '#' + data.chartId,
                xAxis = data.chartXAxis,
                yAxis = data.chartYAxis;

            $(chartId).show();

            var chart = nv.models.multiBarChart();

            chart.xAxis.axisLabel(xAxis.label);
            if (xAxis.format) {
                chart.xAxis.tickFormat(d3.format(xAxis.format));
            }

            chart.yAxis.axisLabel(yAxis.label);
            if (yAxis.format) {
                chart.yAxis.tickFormat(d3.format(yAxis.format));
            }

            chart.showControls(chartConfig.showControls);
            chart.showLegend(chartConfig.showLegend);
            chart.reduceXTicks(chartConfig.reduceXTicks);
            chart.rotateLabels(chartConfig.rotateLabels);
            chart.tooltips(chartConfig.tooltips);
            // Customize tooltip message
            if (data.chartTooltipFormat) {
                chart.tooltipContent(function (key, y, e) { return e + data.chartTooltipFormat + y; });
            }
            chart.stacked(chartConfig.stacked);
            chart.margin(chartConfig.margin);
            chart.staggerLabels(chartConfig.staggerLabels);
            chart.multibar.groupSpacing(chartConfig.groupSpacing);
            chart.multibar.forceY(chartConfig.forceY);

            d3.select(chartId + ' svg')
                .datum(chartData)
                .transition().duration(500).call(chart);

            nv.utils.windowResize(chart.update);

            return chart;
        });
    };
    return { init: init };
});
