function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    var calc = {},
        births = new HSPHBirthCounter(),
        regLength = new HSPHLengthStats();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            if (agEntry) {
                births.rereduce(agEntry);
                regLength.rereduce(agEntry);
            }
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            births.reduce(curEntry);
            regLength.reduce(curEntry);
        }
    }
    extend(calc, births.getResult(), regLength.getResult());
    return calc;
}