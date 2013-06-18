function (key, values, rereduce) {
    var result = {};

    for (var i = 0; i < values.length; i++) {
        var data = values[i];

        if (typeof data === 'number') {
            // working days, reduce not applicable
            return 0;
        } else {
            for (var key in data) {
                if (typeof result[key] === "undefined") {
                    result[key] = data[key];
                } else {
                    result[key] += data[key];
                }
            }
        }
    }

    return result;
}
