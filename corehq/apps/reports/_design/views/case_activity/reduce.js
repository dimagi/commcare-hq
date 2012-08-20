function(keys, values, rereduce) {
    var calc = {
        ownerCounts: {},
        userIdCounts: {},
        typeCounts: {}
    };

    function sum_like_values(current, agEntry) {
        for (var key in agEntry) {
            log(key);
            if (!current[key])
                current[key] = agEntry[key];
            else
                current[key] += agEntry[key];
        }
    }

    function increment(dict, key) {
        if(key)
            if (!dict[key])
                dict[key] = 1;
            else
                dict[key] += 1;

    }

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            log("rereduce");
//            sum_like_values(calc.ownerCounts, agEntry.ownerCounts);
            sum_like_values(calc.userIdCounts, agEntry.userIdCounts);
            sum_like_values(calc.typeCounts, agEntry.typeCounts);
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            increment(calc.ownerCounts, curEntry.owner_id);
            increment(calc.userIdCounts, curEntry.user_id);
            increment(calc.typeCounts, curEntry.type);
        }
    }
    log(calc);
    return calc;
}