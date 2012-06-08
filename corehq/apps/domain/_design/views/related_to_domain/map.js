function(doc) {
    if (doc.domain) {
        emit(doc.domain, doc);
    }
}