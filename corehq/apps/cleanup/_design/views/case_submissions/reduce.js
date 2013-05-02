function (key, values) {
    var i, value;
    for(i = 0; i < values.length; i += 1) {
        if (value === undefined) {
            value = {
                count: values[i].count,
                start: values[i].start,
                end:   values[i].end
            };
        } else {
            value.count += values[i].count;
            value.start = values[i].start < value.start ? values[i].start : value.start;
            value.end   = values[i].end   > value.end   ? values[i].end   : value.end;
        }
    }
    return value;
}