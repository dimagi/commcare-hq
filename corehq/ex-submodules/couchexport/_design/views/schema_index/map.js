function(doc) {
    // !code util/schema.js
    tag = getExportTagValue(doc);
    if (tag) {
        var key = [];
        if (isArray(tag)) {
            for (var i = 0; i < tag.length; i++) {
                key.push(tag[i]);
            }
        } else {
            key.push(tag);
        }
        key.push(getExportDateValue(doc));
        emit(key, null);
    }
}
