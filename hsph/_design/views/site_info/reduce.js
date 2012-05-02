function(keys, values, rereduce) {
    var calc = {};

    if (!rereduce) {
        for (var j in values) {
            var curEntry = values[j];
            if (curEntry.facilityName &&
                    (!calc.facilityName ||
                    (new Date(calc.updateDate) < new Date(curEntry.updateDate))) ) {
                    calc.facilityName = curEntry.facilityName;
                    calc.updateDate = curEntry.updateDate;
            }
        }
    }

    return calc;
}