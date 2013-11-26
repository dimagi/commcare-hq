var height = 400;

function pieChart(id, report) {
    var wedges = [
        {
            key: "Days Used",
            y: report.days_used,
        },
        {
            key: "Days Missed",
            y: report.days_missed,
        }
    ];

    nv.addGraph(function() {
        var chart = nv.models.pieChart()
            .x(function(d) { return d.key })
            .y(function(d) { return d.y })
            .color(d3.scale.category10().range())
            .height(height)
            .valueFormat(d3.format('d'));

          d3.select('#'+id)
            .datum(wedges)
            .transition().duration(1200)
            .attr('height', height)
            .call(chart);

        chart.dispatch.on('stateChange', function(e) { nv.log('New State:', JSON.stringify(e)); });

        return chart;
    });
}


function barChart(id, weekly) {
    var weeks = [];
    weekly.forEach(function (week) {
        weeks.push({
            'label': week[0],
            'value': week[1],
        });
    });
    var chartData = [{
        key: 'something',
        values: weeks,
    }];
    nv.addGraph(function() {
        var chart = nv.models.discreteBarChart()
            .x(function(d) { return d.label })
            .y(function(d) { return d.value })
            .staggerLabels(false)
            .tooltips(false)
            .showValues(true)
            .valueFormat(d3.format('d'));

        d3.select("#"+id)
            .datum(chartData)
            .attr('height', height)
            .call(chart);

        nv.utils.windowResize(chart.update);
        return chart;
    });
}
