// Contains helper functions for rendering nvd3 multibar charts with data pulled from an elastic search histogram filter

var DAY_VALUE = 86400000;
function isInt(n) {
    return typeof n === 'number' && parseFloat(n) == parseInt(n, 10) && !isNaN(n);
}

function intervalize(vals, start, end, interval) {
    var ret = [];
    for (var t = start; t <= end; t += interval) {
        ret.push({x: t, y: 0});
    }
    for (var i = 0; i < vals.length; i++){
        var index = Math.floor((vals[i].x - start) / interval)
        if (index >= 0) {
            ret[index].y += vals[i].y;
        }
    }
    return ret;
}

function swap_prop_names(obj, from_to_map) {
    var ret_obj = {};
    _.each(from_to_map, function (v, k) { ret_obj[v] = obj[k] });
    return ret_obj;
}

function find(collection, filter) {
    for (var i = 0; i < collection.length; i++) {
        if (filter(collection[i], i, collection)) {
            return i;
        }
    }
    return -1;
}

function trim_data(data) {
    /**
     * Removes the empty entries from the ends of the data
     */
    function get_first(arr) {
        return find(arr, function (o) { return o.y > 0 });
    }
    function get_last(arr) {
        var anarr = arr.slice(0);
        anarr.reverse();
        var reverse_index = get_first(anarr);
        return reverse_index > -1 ? arr.length - reverse_index : -1;
    }
    var gt_zero = function (n) {return n > 0};

    var firsts = _.filter(_.map(data, function(d) { return get_first(d.values); }), gt_zero);
    var lasts = _.filter(_.map(data, function(d) { return get_last(d.values); }), gt_zero);
    var first = firsts.length > 0 ? Math.min.apply(null, firsts) : 0;
    var last = lasts.length > 0 ? Math.max.apply(null, lasts) : data[0].values.length;

    return _.map(data, function(d){
        d.values = d.values.splice(first, last);
        return d;
    })
}

function format_data(data, start, end) {
    var ret = [];
    _.each(data, function (vals, name) {
        vals = _.map(vals, function(o) { return swap_prop_names(o, {time: "x", count: "y"})});
        vals = intervalize(vals, start, end, DAY_VALUE);
        ret.push({key: name, values: vals});
    });
    return trim_data(ret);
}

function formatDataForLineGraph(data) {
    ret = {"key": data.key, "values": []};
    var total = 0
    for (var i = 0; i < data.values.length; i++) {
        total += data.values[i].y;
        ret.values.push([data.values[i].x, total])
    }
    return ret
}

function loadCharts(xname, data, starting_time, ending_time) {
    for (var key in data) {
        if (data.hasOwnProperty(key)) {
            if (data[key].length > 0) {
                if (starting_time > data[key][0].time ){
                    starting_time = data[key][0].time;
                }
                if (ending_time < data[key][data[key].length-1].time ){
                    ending_time = data[key][data[key].length-1].time;
                }
            }
        }
    }

    var domain_data = format_data(data, starting_time, ending_time);
    var cum_domain_data = _.map(domain_data, formatDataForLineGraph);

    var bar_chart = addHistogram("#bar-chart svg", xname, domain_data);
    var cum_chart = addLineGraph("#cumulative-chart svg", xname, cum_domain_data);
    var stacked_cum_chart = addStackedAreaGraph("#stacked-cumulative-chart svg", xname, cum_domain_data);

    return {
        "bar-chart": bar_chart,
        "cumulative-chart": cum_chart,
        "stacked-cumulative-chart": stacked_cum_chart
    }
}

function addHistogram(selector, xname, data) {
    var chart = nv.models.multiBarChart().color(d3.scale.category10().range());
    chart = formatChart(chart, selector, xname, data);
    nv.addGraph(function() { return chart });
    return chart;
}

function addLineGraph(selector, xname, data) {
    var chart = nv.models.lineChart()
                  .x(function(d) { return d[0] })
                  .y(function(d) { return d[1] })
                  .color(d3.scale.category10().range());
    chart = formatChart(chart, selector, xname, data);
    nv.addGraph(function() { return chart });
    return chart;
}

function addStackedAreaGraph(selector, xname, data) {
    var chart = nv.models.stackedAreaChart()
                  .x(function(d) { return d[0] })
                  .y(function(d) { return d[1] })
                  .color(d3.scale.category10().range());
    chart = formatChart(chart, selector, xname, data);
    nv.addGraph(function() { return chart });
    return chart;
}

function formatChart(chart, selector, xname, data) {
    chart.xAxis
        .axisLabel('Date')
        .tickFormat(function(d){return d3.time.format.utc('%d-%b-%Y')(new Date(d));});

    chart.yAxis
        .tickFormat(d3.format(',.1d'))
        .axisLabel(xname);

    d3.select(selector)
        .datum(data)
        .transition().duration(500)
        .call(chart);

    nv.utils.windowResize(chart.update);

    return chart;
}
