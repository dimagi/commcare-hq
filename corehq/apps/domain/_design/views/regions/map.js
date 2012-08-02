function (doc) {
    if (doc.doc_type === "Domain" && doc.region) {
        emit(doc.region, null);
    }
}