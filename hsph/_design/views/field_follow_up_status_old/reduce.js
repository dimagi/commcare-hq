function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    var calc = {
        totalFollowedUpByCallCenter: 0,
        totalFollowedUpByDCO: 0
    },
        births = new HSPHBirthCounter();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            births.rereduce(agEntry);

            calc.totalFollowedUpByCallCenter += agEntry.totalFollowedUpByCallCenter;
            calc.totalFollowedUpByDCO += agEntry.totalFollowedUpByDCO;
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            births.reduce(curEntry);

            if (curEntry.dccFollowUp)
                calc.totalFollowedUpByCallCenter += 1;
            else if (curEntry.dcoFollowUp)
                calc.totalFollowedUpByDCO += 1;
        }
    }
    extend(calc, births.getResult());
    return calc;
}