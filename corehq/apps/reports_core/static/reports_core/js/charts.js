var charts = (function() {
    var fn = {};
    var renderPie = function (config, data, svgSelector) {
        return function () {
            // preaggregate the data in the case of multiple levels of aggregation
            // todo: this could be done on the server side too which is probably more efficient
            var aggregatedData = [];
            var aggregatedDataDict = {};
            var current, aggregation, record;
            for (var i = 0; i < data.length; i++) {
                current = data[i];
                aggregation = current[config.aggregation_column];
                if (!aggregatedDataDict.hasOwnProperty(aggregation)) {
                    record = {
                        x: aggregation,
                        y: 0
                    };
                    aggregatedDataDict[aggregation] = record;
                    aggregatedData.push(record);
                } else {
                    record = aggregatedDataDict[aggregation];
                }
                record.y += current[config.value_column];
            }

            var chart = nv.models.pieChart()
                .showLabels(true);

            d3.select(svgSelector)
                .datum(aggregatedData)
                .transition()
                .duration(500)
                .call(chart)
            ;
            nv.utils.windowResize(chart.update);
            return chart;
        };
    };

    var renderMultibarAggregate = function (config, data, svgSelector) {
        return function() {
            var transformedDataDict = {};
            var transformedData = [];
            var secondaryValues = {};
            var record, primary, current, secondary, value;  // loop variables

            // first create intermediate data structures to make it easy to generate
            // the formatted chart data.
            // this also aggregates if there are any duplicate key pairs in the data set.
            for (var i = 0; i < data.length; i++) {
                current = data[i];
                primary = current[config.primary_aggregation];
                if (!transformedDataDict.hasOwnProperty(primary)) {
                    record = {};
                    transformedDataDict[primary] = record;
                } else {
                    record = transformedDataDict[primary];
                }
                if (!record.hasOwnProperty(current[config.secondary_aggregation])) {
                    record[current[config.secondary_aggregation]] = 0;
                }
                secondaryValues[current[config.secondary_aggregation]] = null;
                record[current[config.secondary_aggregation]] += current[config.value_column];
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
                            });
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

            d3.select(svgSelector)
                .datum(transformedData)
                .call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        };
    };

    var renderMultibar = function (config, data, svgSelector) {
        return function() {
            var valuesDict = {};
            var chartData =[];
            var i, j, current, record;

            // initialize records
            for (i = 0; i < config.y_axis_columns.length; i++) {
                record = {
                    key: config.y_axis_columns[i].display,
                    values: []
                };
                valuesDict[config.y_axis_columns[i].column_id] = record;
                chartData.push(record);
            }

            for (i = 0; i < data.length; i++) {
                current = data[i];
                for (j = 0; j < config.y_axis_columns.length; j++) {
                    record = valuesDict[config.y_axis_columns[j].column_id];
                    record.values.push({
                        x: current[config.x_axis_column] || '',
                        y: parseFloat(current[config.y_axis_columns[j].column_id])
                    });
                }
            }
            var chart = nv.models.multiBarChart()
                .transitionDuration(350)
                .reduceXTicks(true)
                .rotateLabels(0)
                .showControls(true)
                .groupSpacing(0.1)
                .stacked(config.is_stacked || false)
            ;

            d3.select(svgSelector)
                .datum(chartData)
                .call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        };
    };

    var chartMap = {
        'pie': renderPie,
        'multibar': renderMultibar,
        'multibar-aggregate': renderMultibarAggregate
    };

    fn.render = function (configs, data, chartContainer) {
        chartContainer.show();
        chartContainer.empty();
        for (var i = 0; i < configs.length; i++) {
            var config = configs[i];
            if (chartMap[config.type] === undefined) {
                console.error("Bad chart configuration: " + config.type);
            } else {
                if (config.title) {
                    $('<h2 />').text(config.title).appendTo(chartContainer);
                }
                var $svg = d3.select(chartContainer[0]).append("svg");
                var id = 'chart-' + i;
                $svg.attr({id: id, width: "50%", height: "200"});
                nv.addGraph(chartMap[config.type](config, data, '#' + id));
            }
        }
    };
    return fn;

})();
