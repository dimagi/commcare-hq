function typeOf(value) {
    // from Crockford himself: http://javascript.crockford.com/remedial.html
    var s = typeof value;
    if (s === 'object') {
        if (value) {
            if (Object.prototype.toString.call(value) == '[object Array]') {
                s = 'array';
            }
        } else {
            s = 'null';
        }
    }
    return s;
}

function isArray(obj) {
    return typeOf(obj) === "array";
}

function get_repeats(data, repeat_filter) {
    repeat_filter = (typeof repeat_filter === "undefined") ? function(r) {return r} : repeat_filter;
    if (!isArray(data)) {
        data = [data];
    }
    ret = [];
    for (var i = 0; i < data.length; i++) {
        if (repeat_filter(data[i])) ret.push(data[i]);
    }
    return ret;
}

function get_from_repeats(data, what_to_get, repeat_filter) {
    repeat_filter = (typeof repeat_filter === "undefined") ? function(r) {return r} : repeat_filter;
    data = get_repeats(data, repeat_filter);
    ret = [];
    for (var i = 0; i < data.length; i++) {
        ret.push(data[i][what_to_get]);
    }
    return ret;
}

function count_in_repeats(data, what_to_count, repeat_filter) {
    repeat_filter = (typeof repeat_filter === "undefined") ? function(r) {return r} : repeat_filter;
    data = get_repeats(data, repeat_filter);
    var total = 0;
    for (var i = 0; i < data.length; i++) {
       total += parseInt(data[i][what_to_count], 10) || 0;
    }
    return total;
}
