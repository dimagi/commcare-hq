function(keys, values, rereduce) {
    var calc = {
        totalBirths: 0,
        totalFollowedUpByCallCenter: 0,
        totalFollowedUpByDCO: 0
    };

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            calc.totalBirths += agEntry.totalBirths;
            calc.totalFollowedUpByCallCenter += agEntry.totalFollowedUpByCallCenter;
            calc.totalFollowedUpByDCO += agEntry.totalFollowedUpByDCO;
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            if (curEntry.dccFollowUp)
                calc.totalFollowedUpByCallCenter += 1;
            else if (curEntry.dcoFollowUp)
                calc.totalFollowedUpByDCO += 1;
            calc.totalBirths += curEntry.numBirths;
        }
    }
    return calc;
}