function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    var calc = {
        workingDays: new Array()
    },
        births = new HSPHBirthCounter(),
        regTime = new HSPHLengthStats(),
        followupStats = new HSPHDCCFollowupStats();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            births.rereduce(agEntry);
            regTime.rereduce(agEntry);
            followupStats.rereduce(agEntry);
            for (var d in agEntry.workingDays)
                if (calc.workingDays.indexOf(agEntry.workingDays[d]) < 0)
                    calc.workingDays.push(agEntry.workingDays[d]);
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            births.reduce(curEntry);
            regTime.reduce(curEntry);
            followupStats.reduce(curEntry);
            var endDate = new Date(curEntry.timeEnd);
            endDate = endDate.toDateString();
            if (calc.workingDays.indexOf(endDate) < 0)
                calc.workingDays.push(endDate);
        }
    }
    calc.totalWorkingDays = calc.workingDays.length;
    extend(calc, births.getResult(), regTime.getResult(), followupStats.getResult());
    return calc;
}