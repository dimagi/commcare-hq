// Contains helper functions for rendering nvd3 multibar charts with data pulled from an elastic search histogram filter

var DAY_VALUE = 86400000;
function isInt(n) {
    return typeof n === 'number' && parseFloat(n) == parseInt(n, 10) && !isNaN(n);
}

function prependToArray(value, oldArray) {
    var i, len = oldArray.length + 1,
        newArray = new Array(len);
    newArray[0] = value;
    return newArray.concat(oldArray);
}

function format_data(data, starting_time, ending_time) {

    function format_data_entry(name, entry) {
        /*
         * Takes in the entries dictionary returned in a es date histogram facet and converts that data for use in nvd3
         */
        entry.sort(function(x, y) {return x.time > y.time});

        var values = [];
        for (var day = starting_time, index = 0; day <= ending_time; day += DAY_VALUE) {
            if (entry.length > 0 && index < entry.length && entry[index].time < day) {
                values.push({x: day, y: entry[index].count});
                index++;
            } else {
//            values.push({x: day, y: 0});
                if (index > 0 && index < entry.length) values.push({x: day, y: 0});
            }
        }

        var ret = {
            key: name,
            values: values
        };
        if (values.length > 0) {
            ret.firsttime = values[0].x;
            ret.lasttime = values[values.length-1].x;
        }
        return ret
    }

    //convert data into proper format
    var formatted_data = [];
    for (var key in data) {
        if (data.hasOwnProperty(key)) {
            var hd = data[key];
            formatted_data.push(format_data_entry(key, hd));
        }
    }

    // fill in each entry with empty data beginning from the startdate to the enddate
    var first = Math.max.apply(null, _.filter(_.map(formatted_data, function(fd) { return fd.firsttime; }), isInt));
    var last = Math.max.apply(null, _.filter(_.map(formatted_data, function(fd) { return fd.lasttime; }), isInt));
    if (first !== -Infinity && last !== -Infinity) {
        _.each(formatted_data, function(entry) {
            if (entry.values.length <= 0) {
                for (var day = first; day <= last; day += DAY_VALUE) {
                    entry.values.push({x: day, y: 0});
                }
            }

            for (var day = first; day < entry.values[0]; day += DAY_VALUE) {
                prependToArray({x: day, y: 0}, entry.values);
            }
            for (var day = entry.values[entry.values.length-1]; day <= last; day += DAY_VALUE) {
                entry.values.push({x: day, y: 0});
            }
        });
    }

    return formatted_data;
}

function addHistogram(element_id, xname, data, starting_time, ending_time) {
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

    chart = nv.addGraph(function() {
        var chart = nv.models.multiBarChart();

        chart.xAxis
            .axisLabel('Date')
            .tickFormat(function(d){return d3.time.format('%d-%b')(new Date(d));});

        chart.yAxis
            .tickFormat(d3.format(',.1f'))
            .axisLabel(xname);

        chart.margin({top: 30, right: 20, bottom: 50, left: 80});

        d3.select('#' + element_id + ' svg')
            .datum(domain_data)
            .transition().duration(500).call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    });
}
