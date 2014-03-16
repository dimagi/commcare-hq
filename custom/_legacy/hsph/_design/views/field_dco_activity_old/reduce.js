function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    var calc = {},
        registrationStats = new HSPHLengthStats(),
        births = new HSPHBirthCounter(),
        siteVisitStats = new HSPHSiteVisitStats(),
        homeVisitStats = new HSPHHomeVisitStats();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            if (agEntry) {
                births.rereduce(agEntry);
                registrationStats.rereduce(agEntry);
                siteVisitStats.rereduce(agEntry);
                homeVisitStats.rereduce(agEntry);
            }
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            if (curEntry.birthReg) {
                births.reduce(curEntry);
                registrationStats.reduce(curEntry);
            } else if (curEntry.siteVisit) {
                siteVisitStats.reduce(curEntry);
            }
            homeVisitStats.reduce(curEntry);
        }
    }

    extend(calc, births.getResult(),
               registrationStats.getResult(),
               siteVisitStats.getResult(),
               homeVisitStats.getResult());
    return calc;
}