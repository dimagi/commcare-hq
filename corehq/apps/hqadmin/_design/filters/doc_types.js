function (doc, req) {
    var doc_types_string = req.query.doc_types;
    if (doc_types_string) {
        var doc_types = doc_types_string.split(' ');
        if (doc_types.indexOf(doc.doc_type) >= 0) {
            return true;
        }
    }
    return false;
}
