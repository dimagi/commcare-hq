function (doc) {
    if (doc.doc_type && doc.domain) {
        emit(["by_type", doc.doc_type, doc.domain], null);
        emit(["by_domain", doc.domain, doc.doc_type], null);
    }
}
