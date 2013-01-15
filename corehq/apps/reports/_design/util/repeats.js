function get_repeats(data, repeat_filter) {
    if (!(data instanceof Array)) data = [data];
    ret = [];
    for (var i = 0; i < data.length; i++) {
        if (repeat_filter(data[i])) ret.push(data[i]);
    }
    return ret;
}

function count_in_repeats(data, what_to_count) {
    if (!(data instanceof Array)) data = [data];
    var total = 0;
    for (var i = 0; i < data.length; i++) {
       total += parseInt(data[i][what_to_count], 10) || 0;
    }
    return total;
}
