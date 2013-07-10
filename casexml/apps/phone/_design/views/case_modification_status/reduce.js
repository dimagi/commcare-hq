function (key, values, rereduce) {
    // Return the maximum string value.
    var empty = '';
    var max = empty;
    for(var i = 0; i < values.length; i++) {
        if (typeof values[i] == 'string') {
            max = max > values[i] ? max : values[i];
        }
    }
    return max;
}
