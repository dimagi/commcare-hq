function(keys, values, rereduce) {
    var result = {};

    var sumIndicators = [
        'liveBirths', 
        'totalStillBirths', 
        'totalNeonatalMortalityEvents7Days',
        'combinedMortalityOutcomes'
    ];
    
    for (var i = 0; i < values.length; i++) {
        var data = values[i];

        for (var key in data) {
            if (typeof result[key] === "undefined") {
                if (sumIndicators.indexOf(key) !== -1) {
                    result[key + 'Sum'] = data[key];
                }

                result[key] = data[key] ? 1 : 0;
            } else {
                if (sumIndicators.indexOf(key) !== -1) {
                    result[key + 'Sum'] += data[key];
                }
                result[key] += data[key] ? 1 : 0;
            }
        }
    }

    return result;
}
