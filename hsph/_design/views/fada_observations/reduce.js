function (key, values, rereduce) {
    // The only useful reduces are:
    //
    //  - group=false with a key that includes up to and including process_sbr_no
    //  - using group_level so a reduce is run for each different key up to and
    //    including process_sbr_no
    //
    //  Therefore, we can use logical OR as the reduce function for each data
    //  value, because it would be meaningless anyway if you tried to reduce
    //  across multiple process_sbr_no.
    
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
