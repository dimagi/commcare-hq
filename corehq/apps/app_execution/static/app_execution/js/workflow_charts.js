'use strict';
hqDefine("app_execution/js/workflow_charts", [
    'jquery',
    'moment/moment',
    'd3/d3.min',
    'nvd3/nv.d3.latest.min',  // version 1.1.10 has a bug that affects line charts with multiple series
    'commcarehq',
], function (
    $, moment, d3, nv
) {

    function getSeries(data, includeSeries) {
        return includeSeries.map((seriesMeta) => {
            return {
                // include key in the label to differentiate between series with the same label
                key: `${data.label}${seriesMeta.label}[${data.key}]`,
                values: data.values.map((item) => {
                    return {
                        x: moment(item.date),
                        y: item[seriesMeta.key],
                    };
                }),
            };
        });
    }

    function buildChart(yLabel) {
        let chart = nv.models.lineChart()
            .showYAxis(true)
            .showXAxis(true);

        chart.yAxis
            .axisLabel(yLabel);
        chart.forceY(0);
        chart.xScale(d3.time.scale());
        chart.margin({left: 80, bottom: 100});
        chart.xAxis.rotateLabels(-45)
            .tickFormat(function (d) {
                return moment(d).format("MMM DD [@] HH");
            });

        nv.utils.windowResize(chart.update);
        return chart;
    }

    function setupTimingChart(data, includeSeries) {
        const timingSeries = data.timing.flatMap((series) => getSeries(series, includeSeries));

        nv.addGraph(() => {
            let chart = buildChart(gettext("Seconds"));
            chart.yAxis.tickFormat(d3.format(".1f"));
            // remove the key from the label
            chart.legend.key((d) => d.key.split("[")[0]);
            chart.tooltip.keyFormatter((d) => {
                return d.split("[")[0];
            });

            d3.select('#timing_linechart svg')
                .datum(timingSeries)
                .call(chart);

            return chart;
        });
    }

    function setupStatusChart(data) {
        const colors = {
            "Success": "#6dcc66",
            "Error": "#f44",
        };
        let seriesData = data.status.map((series) => {
            return {
                key: series.key,
                values: series.values.map((item) => {
                    return {
                        x: moment(item.date),
                        y: item.count,
                    };
                }),
                color: colors[series.key],
            };
        });

        nv.addGraph(() => {
            let chart = buildChart(gettext("Chart"));

            d3.select('#status_barchart svg')
                .datum(seriesData)
                .call(chart);

            return chart;
        });
    }

    $(document).ready(function () {
        const data = JSON.parse(document.getElementById('chart_data').textContent);
        const includeSeries = JSON.parse(document.getElementById('timingSeries').textContent);
        setupTimingChart(data, includeSeries);
        setupStatusChart(data);
    });
});
