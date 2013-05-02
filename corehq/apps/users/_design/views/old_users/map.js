function (doc) {
    if (doc.doc_type === "CouchUser") {
        emit(doc._id, null);
    }
}