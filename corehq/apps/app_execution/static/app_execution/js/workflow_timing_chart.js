/* globals moment */
hqDefine("app_execution/js/workflow_timing_chart", function () {
    function setupLineChart(data) {
        const timingSeries = [
            {
                key: 'Avg Timing',
                values: _.map(data, function (item) {
                    return {
                        x: moment(item.date),
                        y: item.avg_duration,
                    };
                }),
            },
            {
                key: 'Max Timing',
                values: _.map(data, function (item) {
                    return {
                        x: moment(item.date),
                        y: item.max_duration,
                    };
                }),
            },
        ];
        nv.addGraph(function () {
            let chart = nv.models.lineChart()
                .showYAxis(true)
                .showXAxis(true);

            chart.yAxis.tickFormat(d3.format(".1fs"));
            chart.forceY(0);
            chart.xScale(d3.time.scale());
            chart.margin({bottom: 60});
            chart.xAxis.rotateLabels(-45)
                .tickFormat(function (d) {
                    return moment(d).format("MMM DD [@] HH");
                });
            d3.select('#timing_linechart svg')
                .datum(timingSeries)
                .call(chart);

            nv.utils.windowResize(function () {
                chart.update();
            });

            return chart;

        });
    }

    $(document).ready(function () {
        const chartData = JSON.parse(document.getElementById('chart_data').textContent);
        setupLineChart(chartData);
    });
});
