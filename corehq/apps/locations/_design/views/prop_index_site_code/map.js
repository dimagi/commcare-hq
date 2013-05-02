function(doc) {
    if (doc.doc_type == "Location") {
        var val = doc.site_code;
        if (val == null) {
            return;
        }
        if (typeof val == 'string') {
            val = val.toLowerCase();
        }

        var path = doc.lineage.slice(0);
        path.push(null);

        for (var i = 0; i < path.length; i++) {
            emit([doc.domain, val, path[i], i + 1], null);
        }
    }
}
