function(keys, values, rereduce) {
    // !code util/hsph_reduce.js

    function keepUsersUnique(newList, oldList) {
        for (var i in oldList) {
            var ind = newList.indexOf(oldList[i]);
            if (ind < 0)
                newList.push(oldList[i]);
        }
    }

    var calc = {
        numProcessData: 0,
        numOutcomeData: 0,
        activeCollectors: [],
        activeTLs: []
    },
        births = new HSPHBirthCounter(),
        facStat = new HSPHFacilityStatusStats();

    if (rereduce) {
        for (var i in values) {
            var agEntry = values[i];
            births.rereduce(agEntry);
            facStat.rereduce(agEntry);
            calc.numProcessData += agEntry.numProcessData;
            calc.numOutcomeData += agEntry.numOutcomeData;
            keepUsersUnique(calc.activeCollectors, agEntry.activeCollectors);
            keepUsersUnique(calc.activeTLs, agEntry.activeTLs);
        }
    } else {
        for (var j in values) {
            var curEntry = values[j];
            births.reduce(curEntry);
            facStat.reduce(curEntry);
            calc.numProcessData += (curEntry.processDataType) ? 1 : 0;
            calc.numOutcomeData += (curEntry.outcomeDataType) ? 1 : 0;
            if  (curEntry.userId) {
                var uind = calc.activeCollectors.indexOf(curEntry.userId),
                    tlind = calc.activeTLs.indexOf(curEntry.DCTL);
                if (uind < 0)
                    calc.activeCollectors.push(curEntry.userId);
                if (tlind < 0)
                    calc.activeTLs.push(curEntry.DCTL);
            }
        }
    }

    extend(calc, births.getResult(), facStat.getResult());
    return calc;
}