function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    var calc = {},
        births = new HSPHBirthCounter(),
        siteVisits = new HSPHSiteVisitStats();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            if (agEntry) {
                births.rereduce(agEntry);
                siteVisits.rereduce(agEntry);
            }
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            if (curEntry.birthReg)
                births.reduce(curEntry);
            siteVisits.reduce(curEntry);
        }
    }

    extend(calc, births.getResult(), siteVisits.getResult());
    return calc;
}