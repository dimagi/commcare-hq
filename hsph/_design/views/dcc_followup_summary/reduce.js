function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    var calc = {
        numCasesFollowedUpByDay8: 0,
        numCasesFollowedUpBetweenDays9and13: 0,
        numCasesWithContactTransferredToField: 0,
        numCasesWithNoOutcomes: 0
    },
        births = new HSPHBirthCounter();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            births.rereduce(agEntry);
            calc.numCasesFollowedUpByDay8 += agEntry.numCasesFollowedUpByDay8;
            calc.numCasesFollowedUpBetweenDays9and13 += agEntry.numCasesFollowedUpBetweenDays9and13;
            calc.numCasesWithContactTransferredToField += agEntry.numCasesWithContactTransferredToField;
            calc.numCasesWithNoOutcomes += agEntry.numCasesWithNoOutcomes;
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            births.reduce(curEntry);
            if (curEntry.atDay8)
                calc.numCasesFollowedUpByDay8 += 1;
            else if (curEntry.between9and13)
                calc.numCasesFollowedUpBetweenDays9and13 += 1;

            if (curEntry.contactProvided && curEntry.followupTransferred)
                calc.numCasesWithContactTransferredToField += 1;
            else if (curEntry.followupWaitlisted)
                calc.numCasesWithNoOutcomes += 1;
        }
    }
    extend(calc, births.getResult());
    return calc;
}