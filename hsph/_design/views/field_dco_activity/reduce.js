function(keys, values, rereduce) {
    var calc = {
        numFacilitiesVisited: 0,
        numFacilityVisits: 0,
        lessThanTwoWeeklyFacilityVisits: 0,
        totalBirths: 0,
        totalBirthsWithoutContact: 0,
        totalRegistrationTime: 0,
        totalRegistrations: 0,
        numHomeVisits: 0,
        numHomeVisitsCompleted: 0,
        numHomeVisitsOpenAt21: 0,
        siteVisitStats: {}
    };

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            calc.totalBirths += agEntry.totalBirths;
            calc.totalBirthsWithoutContact += agEntry.totalBirthsWithoutContact;
            if (agEntry.averageRegistrationLength) {
                calc.totalRegistrationTime += agEntry.averageRegistrationLength;
                calc.totalRegistrations += 1;
            }
            calc.numHomeVisits += agEntry.numHomeVisits;
            calc.numHomeVisitsCompleted += agEntry.numHomeVisitsCompleted;
            calc.numHomeVisitsOpenAt21 += agEntry.numHomeVisitsOpenAt21;

            for (var site in agEntry.siteVisitStats) {
                if (calc.siteVisitStats[site]) {
                    calc.siteVisitStats[site].visits += agEntry.siteVisitStats[site].visits;
                } else {
                    calc.siteVisitStats[site] = {};
                    calc.siteVisitStats[site].visits = agEntry.siteVisitStats[site].visits;
                    calc.siteVisitStats[site].dates = new Array();
                }
                calc.siteVisitStats[site].dates = calc.siteVisitStats[site].dates.concat(agEntry.siteVisitStats[site].dates);
            }
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            if (curEntry.birthReg) {
                calc.totalBirths += curEntry.numBirths;
                if (!curEntry.contactProvided)
                    calc.totalBirthsWithoutContact += curEntry.numBirths;
                calc.totalRegistrationTime += curEntry.registrationLength;
                calc.totalRegistrations ++;

            } else if (curEntry.siteVisit) {
                var siteID = curEntry.siteId;
                if (calc.siteVisitStats[siteID]) {
                    calc.siteVisitStats[siteID].visits += 1;
                } else {
                    calc.siteVisitStats[siteID] = {};
                    calc.siteVisitStats[siteID].visits = 1;
                    calc.siteVisitStats[siteID].dates = new Array();
                }
                calc.siteVisitStats[siteID].dates.push(curEntry.visitDate);
            } else if (curEntry.homeVisit) {
                calc.numHomeVisits += 1;
                calc.numHomeVisitsCompleted += (curEntry.completed) ? 1 : 0;
                calc.numHomeVisitsOpenAt21 += (curEntry.openedAt21) ? 1 : 0;
            }
        }
    }

    if (calc.siteVisitStats) {
        for (var s in calc.siteVisitStats) {
            var visitDates = calc.siteVisitStats[s].dates,
                twoVisitsInAWeek = false;
            for (var a in visitDates) {
                for (var b in visitDates) {
                    if (a != b) {
                        var firstVisit = new Date(a),
                            secondVisit = new Date(b),
                            millisecondsInWeek = 7*24*60*60*1000,
                            millisecondsInDay = 24*60*60*1000;
                        if ((firstVisit.getTime() - secondVisit.getTime() <= millisecondsInWeek)
                            && (firstVisit.getTime() - secondVisit.getTime() > millisecondsInDay) ) {
                            twoVisitsInAWeek = true;
                        }
                    }
                }
            }
            if (!twoVisitsInAWeek)
                calc.lessThanTwoWeeklyFacilityVisits += 1;

            calc.numFacilityVisits += calc.siteVisitStats[s].visits;
            calc.numFacilitiesVisited += 1;
        }
    }

    calc.averageRegistrationLength = (calc.totalRegistrationTime > 0) ? Math.round(calc.totalRegistrationTime/calc.totalRegistrations) : null;
    return calc;
}