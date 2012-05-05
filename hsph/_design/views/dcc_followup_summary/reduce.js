function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    var calc = {},
        births = new HSPHBirthCounter();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            births.rereduce(agEntry);
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            births.reduce(curEntry);

        }
    }
    extend(calc, births.getResult());
    return calc;
}