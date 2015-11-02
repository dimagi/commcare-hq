function (doc) {
    if (doc.domain) {
        emit([doc.domain, doc.doc_type], null);
    }
}
