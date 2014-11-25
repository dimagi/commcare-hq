function (key, values, rereduce) {
    var value = 0,
        i;

    if (rereduce === true) {
        return sum(values);
    }
    for(i = 0; i < values.length; i += 1) {
        if (values[i].hasOwnProperty('attachments')) {
            for (var j in values[i].attachments) {
                if (values[i].attachments.hasOwnProperty(j)) {
                    value += values[i].attachments[j].length;
                }
            }
        }
    }
    return value;
}
