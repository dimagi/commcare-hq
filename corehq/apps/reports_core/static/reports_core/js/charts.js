var charts = (function() {
    var fn = {};
    var renderPie = function (config, data, container) {
        return function () {
            var chart = nv.models.pieChart()
                .x(function(d) { return d[config.aggregation_column]; })
                .y(function(d) { return d[config.value_column]; })
                .showLabels(true);

            d3.select('#charts')
                .datum(data)
                .transition()
                .duration(500)
                .call(chart)
            ;
            nv.utils.windowResize(chart.update);
            return chart;
        }
    };

    var renderMultibar = function (config, data, container) {
        return function() {
            var transformedDataDict = {};
            var transformedData = [];
            var secondaryValues = {};
            var record, primary, current, secondary, value;  // loop variables

            // first create intermediate data structures to make it easy to generate
            // the formatted chart data
            for (var i = 0; i < data.length; i++) {
                current = data[i];
                primary = current[config.primary_aggregation];
                if (!transformedDataDict.hasOwnProperty(primary)) {
                    record = {};
                    transformedDataDict[primary] = record;
                } else {
                    record = transformedDataDict[primary];
                }
                secondaryValues[current[config.secondary_aggregation]] = null;
                record[current[config.secondary_aggregation]] = current[config.value_column];
            }

            // this annoying extra nested loop is because nvd3 appears to choke if the data
            // is not uniform
            for (primary in transformedDataDict) {
                record = {
                    "key": primary,
                    "values": []
                };
                if (transformedDataDict.hasOwnProperty(primary)) {
                    for (secondary in secondaryValues) {
                        if (secondaryValues.hasOwnProperty(secondary)) {
                            if (transformedDataDict[primary].hasOwnProperty(secondary)) {
                                value = transformedDataDict[primary][secondary];
                            } else {
                                value = 0;
                            }
                            record.values.push({
                                'x': secondary,
                                'y': value
                            })
                        }
                    }
                }
                transformedData.push(record);
            }
            var chart = nv.models.multiBarChart()
              .transitionDuration(350)
              .reduceXTicks(true)
              .rotateLabels(0)
              .showControls(true)
              .groupSpacing(0.1)
            ;

            d3.select('#charts')
                .datum(transformedData)
                .call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        };
    };

    var chartMap = {
        'pie': renderPie,
        'multi-bar': renderMultibar
    };

    fn.render = function (config, data, chartContainer) {
        if (chartMap[config.type] === undefined) {
            console.error("Bad chart configuration " + config.type);
        } else {
            chartContainer.show();
            nv.addGraph(chartMap[config.type](config, data, chartContainer));
        }
    }
    return fn;

})();