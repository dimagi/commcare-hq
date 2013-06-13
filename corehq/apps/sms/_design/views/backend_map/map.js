function(doc) {
    if(doc.doc_type === "BackendMapping") {
        var domain = doc.is_global ? "*" : doc.domain;
        emit([domain, doc.prefix], null);
    }
}
