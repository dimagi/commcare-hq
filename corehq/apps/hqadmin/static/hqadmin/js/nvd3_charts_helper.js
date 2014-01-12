// Contains helper functions for rendering nvd3 multibar charts with data pulled from an elastic search histogram filter

var INTERVAL_VALUES = {
    "day": 86400000,
    "week": 86400000 * 7,
    "month": 86400000 * 30,
    "year": 86400000 * 365
};

function isInt(n) {
    return typeof n === 'number' && parseFloat(n) == parseInt(n, 10) && !isNaN(n);
}

function is_data_empty(histo_data) {
    for (var key in histo_data) {
        if (histo_data.hasOwnProperty(key)) {
            if (histo_data[key].length > 0) {
                return false;
            }
        }
    }
    return true;
}

function are_init_values_zero(values) {
    for (var key in values) {
        if (values.hasOwnProperty(key)) {
            if (values[key] > 0) {
                return false;
            }
        }
    }
    return true;
}

function intervalize(vals, start, end, interval) {
    var ret = [];
    for (var t = start; t <= end; t += interval) {
        ret.push({x: t, y: 0});
    }
    for (var i = 0; i < vals.length; i++){
        var index = Math.floor((vals[i].x - start) / interval);
        if (index >= 0) {
            ret[index].y += vals[i].y;
        }
    }
    return ret;
}

function date_to_first_of_month(date_val) {
    var month = new Date(date_val).getUTCMonth();
    var year = new Date(date_val).getUTCFullYear();
    return new Date(Date.UTC(year, month, 1));
}

function where_to_put(vals, time) {
    for (var i = 0; i < vals.length; i++) {
        if (i + 1 < vals.length && vals[i + 1].x <= time) {
            continue;
        }
        return i;
    }
}

function intervalize_months(vals, start, end) {
    var ret = [];
    var current_date = date_to_first_of_month(start), end = date_to_first_of_month(end);
    var current_month = current_date.getUTCMonth();
    var initial_year = current_date.getUTCFullYear();

    while (current_date.valueOf() <= end.valueOf()) {
        ret.push({x: current_date.valueOf(), y: 0});
        current_month += 1;
        current_date = new Date(Date.UTC(initial_year, current_month, 1))
    }

    for (var i = 0; i < vals.length; i++) {
        var index = where_to_put(ret, vals[i].x);
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
    var gte_zero = function (n) {return n >= 0};

    var firsts = _.filter(_.map(data, function(d) { return get_first(d.values); }), gte_zero);
    var lasts = _.filter(_.map(data, function(d) { return get_last(d.values); }), gte_zero);
    var first = firsts.length > 0 ? Math.min.apply(null, firsts) : 0;
    var last = lasts.length > 0 ? Math.max.apply(null, lasts) : data[0].values.length;

    return _.map(data, function(d){
        d.values = d.values.splice(first, last);
        return d;
    })
}

function format_data(data, start, end, interval, no_trim) {
    var ret = [];
    _.each(data, function (vals, name) {
        vals = _.map(vals, function(o) { return swap_prop_names(o, {time: "x", count: "y"})});
        if (interval === 'month') {
            vals = intervalize_months(vals, start, end)
        } else {
            vals = intervalize(vals, start, end, INTERVAL_VALUES[interval]);
        }
        ret.push({key: name, values: vals});
    });

    if (no_trim) {
        return ret;
    }
    return trim_data(ret);
}

function formatDataForCumGraphs(data, init_val) {
    var ret = {"key": data.key, "values": []};
    var total = init_val;
    for (var i = 0; i < data.values.length; i++) {
        total += data.values[i].y;
        ret.values.push([data.values[i].x, total]);
    }
    return ret;
}

function findEnds(data, starting_time, ending_time) {
    var start = ending_time, end = starting_time;
    for (var key in data) {
        if (data.hasOwnProperty(key)) {
            if (data[key].length > 0) {
                if (start > data[key][0].time ){
                    start = data[key][0].time;
                }
                if (end < data[key][data[key].length-1].time ){
                    end = data[key][data[key].length-1].time;
                }
            }
        }
    }
    return {
        start: start,
        end: end
    }
}

function loadCharts(chart_name, xname, data, initial_values, starting_time, ending_time, interval) {
    var ends = findEnds(data, starting_time, ending_time);
    starting_time = ends.start, ending_time = ends.end;
    var domain_data = format_data(data, starting_time, ending_time, interval);
    var cum_domain_data = _.map(domain_data, function (domain_datum) {
        return formatDataForCumGraphs(domain_datum, initial_values[domain_datum.key]);
    });

    var bar_chart = null;
    var cum_chart = null;
    var stacked_cum_chart = null;
    if (!is_data_empty(data)) {
        bar_chart = addHistogram("#" + chart_name + "-bar-chart svg", xname, domain_data);
    }
    if (!is_data_empty(data) || !are_init_values_zero(initial_values)) {
        cum_chart = addLineGraph("#" + chart_name + "-cumulative-chart svg", xname, cum_domain_data);
        stacked_cum_chart = addStackedAreaGraph("#" + chart_name + "-stacked-cumulative-chart svg", xname, cum_domain_data);
    }

    // move the yaxis label to the left a lil
    var yaxislabel = d3.selectAll('.nv-y.nv-axis .nv-axislabel');
    yaxislabel.attr('transform', function(d,i,j) {
        return 'translate (-11, 0), rotate(-90)'
    });

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

var linebreak_txt = " -- ";
function formatChart(chart, selector, xname, data, margin_left) {
    chart.xAxis
        .axisLabel('Date')
        .tickFormat(function(d){return d3.time.format.utc('%b %d' + linebreak_txt + '%Y')(new Date(d));});

    chart.yAxis
        .tickFormat(d3.format(',.1d'))
        .axisLabel(xname);

    d3.select(selector)
        .datum(data)
        .transition().duration(500)
        .call(chart);

    nv.utils.windowResize(chart.update);

    chart.margin({left: margin_left || 75});
    return chart;
}

var insertLinebreaks = function (d) {
    var el = d3.select(this);
    var words = this.textContent.split(linebreak_txt);
    el.text('');

    for (var i = 0; i < words.length; i++) {
        var tspan = el.append('tspan').text(words[i]);
        if (i > 0) {
            tspan.attr('x', 0).attr('dy', '15');
        }
    }
};

function formatDataForLineGraph(data) {
    var starting_time = Infinity, ending_time = 0;
    ends = findEnds(data, starting_time, ending_time);
    starting_time = ends.start, ending_time = ends.end;
    if (starting_time === Infinity) {
        starting_time = undefined, ending_time = undefined;
    }
    data = format_data(data, starting_time, ending_time, INTERVAL_VALUES.day, true);
    return _.map(data, function (datum) {
        var ret = {"key": datum.key, "values": []};
        for (var i = 0; i < datum.values.length; i++) {
            ret.values.push({x: datum.values[i].x, y: datum.values[i].y});
        }
        return ret;
    });
}
