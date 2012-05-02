function(keys, values, rereduce) {
    var calc = {
        totalBirths: 0,
        totalRegistrationTime: 0,
        totalRegistrations: 0
    };

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            calc.totalBirths += agEntry.totalBirths;
            if (agEntry.averageRegistrationLength) {
                calc.totalRegistrationTime += agEntry.averageRegistrationLength;
                calc.totalRegistrations += 1;
            }
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            calc.totalBirths += curEntry.numBirths;
            calc.totalRegistrationTime += curEntry.registrationLength;
            calc.totalRegistrations ++;
        }
    }
    calc.averageRegistrationLength = (calc.totalRegistrationTime > 0) ? Math.round(calc.totalRegistrationTime/calc.totalRegistrations) : null;
    return calc;
}