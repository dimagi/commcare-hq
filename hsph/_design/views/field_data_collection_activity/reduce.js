function(keys, values, rereduce) {
    var calc = {
        totalBirths: 0,
        totalBirthsWithoutContact: 0,
        numFacilityVisits: 0
    };

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            calc.totalBirths += agEntry.totalBirths;
            calc.totalBirthsWithoutContact += agEntry.totalBirthsWithoutContact;
            calc.numFacilityVisits += agEntry.numFacilityVisits;
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            if (curEntry.birthReg) {
                calc.totalBirths += curEntry.numBirths;
                if (!curEntry.contactProvided)
                    calc.totalBirthsWithoutContact += curEntry.numBirths;
            } else if (curEntry.siteVisit)
                calc.numFacilityVisits += 1;
        }
    }

    return calc;
}