function(doc) {
    var path = doc.location_;
    if (path != null) {
        path = path.slice(0);
        path.splice(0, 0, null);
        for (var i = 0; i < path.length; i++) {
            emit([doc.domain, path[i], doc.doc_type, i == path.length - 1], null);
        }
    }
}
