/* globals moment, nv */
hqDefine("app_execution/js/workflow_timing_chart", function () {
    function getSeries(data, includeSeries) {
        return includeSeries.map((seriesMeta) => {
            return {
                // include key in the label to differentiate between series with the same label
                label: `${data.label}${seriesMeta.label}`,
                key: `${data.label}${seriesMeta.label}[${data.key}]`,
                values: data.values.map((item) => {
                    return {
                        x: moment(item.date),
                        y: item[seriesMeta.key],
                    };
                }).filter((item) => item.x && item.y),
            };
        });
    }

    function setupLineChart(data, includeSeries) {
        const timingSeries = data.flatMap((series) => getSeries(series, includeSeries));
        nv.addGraph(function () {
            let chart = nv.models.lineChart()
                .showYAxis(true)
                .showXAxis(true);

            chart.yAxis
                .axisLabel('Seconds')
                .tickFormat(d3.format(".1f"));
            chart.forceY(0);
            chart.xScale(d3.time.scale());
            chart.margin({left: 50, bottom: 60});
            chart.xAxis.rotateLabels(-45)
                .tickFormat(function (d) {
                    return moment(d).format("MMM DD [@] HH");
                });
            // remove the key from the label
            chart.legend.key((d) => d.key.split("[")[0]);
            chart.tooltipContent(function (key, x, y) {
                return '<h3>' + key.split("[")[0] + '</h3>' +
                       '<p>' +  y + ' at ' + x + '</p>';
            });

            d3.select('#timing_linechart svg')
                .datum(timingSeries)
                .call(chart);

            nv.utils.windowResize(chart.update);
            return chart;
        });

    }

    $(document).ready(function () {
        const chartData = JSON.parse(document.getElementById('chart_data').textContent);
        const includeSeries = JSON.parse(document.getElementById('includeSeries').textContent);
        setupLineChart(chartData, includeSeries);
    });
});
