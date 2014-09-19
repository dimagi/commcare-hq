var charts = (function() {
    var fn = {};
    var renderPie = function (config, data, container) {
        container.show();
        nv.addGraph(function() {
            var chart = nv.models.pieChart()
                .x(function(d) { return d[config.aggregation_column]; })
                .y(function(d) { return d[config.value_column]; })
                .showLabels(true);

            d3.select('#charts')
                .datum(data)
                .transition()
                .duration(500)
                .call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        });
    };

    var chartMap = {
        'pie': renderPie
    };

    fn.render = function (config, data, chartContainer) {
        if (chartMap[config.type] === undefined) {
            console.error("Bad chart configuration " + config.type);
        } else {
            chartMap[config.type](config, data, chartContainer);
        }
    }
    return fn;

})();