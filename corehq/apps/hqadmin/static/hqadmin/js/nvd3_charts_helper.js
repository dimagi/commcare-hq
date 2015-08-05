// Contains helper functions for rendering nvd3 multibar charts with data pulled from an elastic search histogram filter

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

function swap_prop_names(obj, from_to_map) {
    var ret_obj = {};
    _.each(from_to_map, function (v, k) { ret_obj[v] = obj[k] });
    return ret_obj;
}

function days_in_year(year) {
    if (is_leap_year(year)) {
        return 366;
    }
    return 365;
}

function is_leap_year(year) {
    return new Date(year, 1, 29).getMonth() == 1;
}

function days_in_month(month, year) {
    return new Date(year, month+1, 0).getDate();
}

function next_interval(date, interval) {
    switch(interval) {
        case "day":
            date.setUTCDate(date.getUTCDate() + 1);
            break;
        case "week":
            date.setUTCDate(date.getUTCDate() + 7);
            break;
        case "month":
            date.setUTCDate(date.getUTCDate() + days_in_month(date.getUTCMonth(), date.getUTCFullYear()));
            break;
        case "year":
            date.setUTCDate(date.getUTCDate() + days_in_year(date.getUTCFullYear()));
            break;
    }
    return date;
}

function fill_in_spaces(vals, start, end, interval) {
    var start_date = new Date(start),
        end_date = new Date(end),
        cur_index = 0,
        ret = [];

    for (var i = start_date; i <= end_date; i=next_interval(i, interval)) {
        if (cur_index < vals.length && vals[cur_index].x === i.getTime()) {
            ret.push(vals[cur_index]);
            cur_index++;
        } else {
            ret.push({x: i.getTime(), y: 0});
        }
    }

    // if there are any real values left over then tack them on to the end
    // this should not happen
    if (cur_index < _.filter(vals, function(n) {return n.y > 0;}).length) {
        ret.concat(vals.slice(cur_index));
        console.log("There were extra values in a response");
    }

    return ret;
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
        vals = _.map(vals, function(o) {
            return swap_prop_names(o, {time: "x", count: "y"});
        });
        vals = fill_in_spaces(vals, start, end, interval);
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

    function real_data(value) {
        return value.count > 0;
    }

    for (var key in data) {
        if (data.hasOwnProperty(key)) {
            if (data[key].length > 0) {
                var filteredData = _.filter(data[key], real_data);
                if (filteredData.length > 0) {
                    if (start > filteredData[0].time){
                        start = filteredData[0].time;
                    }
                    if (end < filteredData[filteredData.length-1].time) {
                        end = filteredData[filteredData.length-1].time;
                    }
                }
            }
        }
    }

    // If there isn't any real data here then reset end and start times
    if (start === ending_time && end === starting_time) {
        start = starting_time;
        end = ending_time;
    }

    return {
        start: start,
        end: end
    };
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
    var si_prefix_formatter = d3.format('.3s'),
        integer_formatter = d3.format(',.1d');

    chart.xAxis
        .axisLabel('Date')
        .tickFormat(function(d){return d3.time.format.utc('%b %d' + linebreak_txt + '%Y')(new Date(d));});

    chart.yAxis
        .tickFormat(function(d){
            if(d >= Math.pow(10,4)){
                return si_prefix_formatter(d);
            }
            return integer_formatter(d);
        })
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
    var starting_time = 0, ending_time = Infinity;
    ends = findEnds(data, starting_time, ending_time);
    starting_time = ends.start, ending_time = ends.end;
    if (starting_time === Infinity) {
        starting_time = undefined, ending_time = undefined;
    }
    data = format_data(data, starting_time, ending_time, 'day', true);
    return _.map(data, function (datum) {
        var ret = {"key": datum.key, "values": []};
        for (var i = 0; i < datum.values.length; i++) {
            ret.values.push({x: datum.values[i].x, y: datum.values[i].y});
        }
        return ret;
    });
}
