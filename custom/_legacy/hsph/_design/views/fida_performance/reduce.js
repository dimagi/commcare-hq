function(keys, values, rereduce) {
    var result = {};

    for (var i = 0; i < values.length; i++) {
        var val = values[i];
        for (var k in val) {
            result[k] = (result[k] || 0) + val[k];
        }
    }

    if (result.birthRegistrations) {
        result.avgBirthRegistrationTime = Math.round(
            result.birthRegistrationTime / result.birthRegistrations);
    }

    if (result.facilityVisits) {
        result.birthRegistrationsPerVisit = Math.round(
            result.birthRegistrations / result.facilityVisits);
    }

    return result;
}
