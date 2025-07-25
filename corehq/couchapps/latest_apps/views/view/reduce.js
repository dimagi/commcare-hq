function (keys, values, rereduce) {
    // return just the doc with the highest version
    var latest_doc = values[0];
    for (i = 1; i < values.length; i++) {
        var doc = values[i];
        if (doc.version > latest_doc.version) {
            latest_doc = doc;
        }
    }
    return latest_doc;
}
