function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    var calc = {
        facilityStatus: -1,
        lastUpdated: null
    };

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            var visited = agEntry.lastUpdated;
            if (!calc.lastUpdated) {
                calc.lastUpdated = visited;
                calc.facilityStatus = agEntry.facilityStatus;
            }else if (new Date(calc.lastUpdated) < new Date(visited)) {
                calc.lastUpdated = visited;
                calc.facilityStatus = agEntry.facilityStatus;
            }

            calc.facilityType = agEntry.facilityType;
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            calc.facilityType = curEntry.IHFCHF;
            var visited = curEntry.updateDate;
            if (!calc.lastUpdated) {
                calc.lastUpdated = visited;
                calc.facilityStatus = curEntry.facilityStatus;
            }else if (new Date(calc.lastUpdated) < new Date(visited)) {
                calc.lastUpdated = visited;
                calc.facilityStatus = curEntry.facilityStatus;
            }

            calc.facilityType = curEntry.IHFCHF;
        }
    }
    return calc;
}