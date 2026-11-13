function (keys, values, rereduce) {
    // return just the doc with the highest version
    var latest_doc = null;
    for (i = 0; i < values.length; i++) {
        var doc = values[i];
        if (!latest_doc || doc.version > latest_doc.version) {
            latest_doc = doc;
        }
    }
    return latest_doc;
}
