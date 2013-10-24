function (key, values, rereduce) {
    var result = {};

    for (var i = 0; i < values.length; i++) {
        var data = values[i];

        for (var key in data) {
            if (key === 'site_id' || key === 'user_id') {
                result[key] = data[key]; 
            } else if (typeof result[key] === "undefined") {
                result[key] = data[key];
            } else {
                result[key] = result[key] || data[key];
            }
        }
    }

    return result;
}
