function(keys, values, rereduce) {
    var calc = {
        errors: 0,
        warnings: 0,
        count: 0
    };

    if (rereduce) {
        for (var j in values) {
            var agVal = values[j];
            calc.errors += agVal.errors;
            calc.warnings += agVal.warnings;
            calc.count += agVal.count;
        }
    } else {
        for (var i in values) {
            var currentVal = values[i];
            calc.errors += (currentVal.isError) ? 1 : 0;
            calc.warnings += (currentVal.isWarning) ? 1 : 0;
            calc.count += 1;
        }
    }
    return calc;
}